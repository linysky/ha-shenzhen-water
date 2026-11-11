"""Read-only 环水管家 API, verified against client version 202."""
import asyncio
import base64
import json
import math
import secrets
from datetime import datetime

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

PATHS = {
    "renew": "CustomerInfo/generaterUtoken",
    "token": "CustomerInfo/generaterCtoken",
    "latest": "BillInfo/GetLatestBillDetails2V30",
    "history": "BillInfo/GetPaidBillDetailListByYearV302",
    "detail": "user/billInfo/BillingInfoBycustomerCodesV30",
}
BASE = "https://szgk.sz-water.com.cn/api/wechat/op/"


class WaterError(Exception):
    """Safe error without server payloads or account credentials."""


class WaterAuthError(WaterError):
    pass


def key(seed):
    if not isinstance(seed, str) or len(seed) < 24:
        raise WaterError("接口密钥格式异常")
    return ("CD3AA097" + seed[8:24] + "CE92AD77").encode()


def encode(body, seed):
    pad = PKCS7(128).padder()
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    cipher = Cipher(algorithms.AES(key(seed)), modes.ECB()).encryptor()
    return base64.b64encode(cipher.update(pad.update(raw) + pad.finalize()) + cipher.finalize()).decode()


def decode(body, seed):
    if not isinstance(body, str):
        return body
    raw = base64.b64decode(body[:7] + body[20:] + body[7:20], validate=True)
    cipher = Cipher(algorithms.AES(key(seed)), modes.ECB()).decryptor()
    unpad = PKCS7(128).unpadder()
    return json.loads(unpad.update(cipher.update(raw) + cipher.finalize()) + unpad.finalize())


def configuration(text):
    try:
        data = json.loads(text)
        headers = {k: data["headers"][k] for k in ("utoken", "openid", "tenantid", "channel")}
        templates = {k: data["templates"][k] for k in PATHS if k != "renew"}
        if not all(isinstance(v, str) and v for v in headers.values()):
            raise ValueError()
        if not all(isinstance(v, dict) for v in templates.values()):
            raise ValueError()
        account = templates["token"]["customercode"]
        if not isinstance(account, str) or not account:
            raise ValueError()
        if templates["history"]["customercode"] != account or templates["detail"]["customerCodes"] != [account]:
            raise ValueError()
        return {"headers": headers, "templates": templates}
    except (ValueError, KeyError, TypeError):
        raise WaterError("会话配置格式不正确") from None


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def bill(row):
    """Explicit allowlist: never expose customer names, addresses or meter IDs."""
    period = str(row.get("costDate", ""))
    try:
        month = datetime.strptime(period, "%Y%m").strftime("%Y-%m")
        if len(period) != 6:
            return None
    except ValueError:
        return None
    result = {"month": month}
    for out, source in {"cubicMeters": "waterConsumption", "waterCost": "waterAmount", "sewageCost": "sewageAmount", "garbageCost": "garbageAmount", "totalCost": "totalAmount", "due": "needpay", "arrears": "hisnetAmount", "lateFee": "lateFee"}.items():
        result[out] = number(row.get(source))
    result["status"] = row.get("paymentStatus") if row.get("paymentStatus") in ("已缴清", "未缴清", "未缴费", "部分缴费") else None
    result["readings"] = []
    for meter in row.get("meterWaterUses") or []:
        item = {"previous": number(meter.get("waterNumberPreTime")), "current": number(meter.get("waterNumber")), "cubicMeters": number(meter.get("waterConsumption"))}
        for out, source in (("previousDate", "meterCheckPreDate"), ("currentDate", "meterCheckMonDate")):
            try:
                item[out] = datetime.fromisoformat(str(meter.get(source)).replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                item[out] = None
        result["readings"].append(item)
    return result


class WaterClient:
    def __init__(self, session, config):
        self.session = session
        self.config = {**config, "headers": dict(config.get("headers", {}))}
        self.ctoken = None
        self.details = {}

    async def request(self, name, body=None):
        seed = secrets.token_hex(16)
        headers = {**self.config["headers"], "04A52C9F": seed}
        if name == "renew":
            headers.pop("utoken", None)
        elif self.ctoken:
            headers["Ctoken"] = self.ctoken
        try:
            async with asyncio.timeout(20):
                async with self.session.post(BASE + PATHS[name], headers=headers,
                    json=encode(body or self.config["templates"][name], seed), allow_redirects=False) as response:
                    if response.status in (401, 403):
                        raise WaterAuthError("深圳水务登录已失效，请重新认证")
                    if response.status != 200:
                        raise WaterError(f"水务接口 HTTP {response.status}")
                    data = decode(await response.json(content_type=None), response.headers.get("04A52C9F"))
            if data.get("code") in (401, "401", 403, "403"):
                raise WaterAuthError("深圳水务登录已失效，请重新认证")
            if data.get("code") != 0:
                raise WaterError("水务接口拒绝请求，请检查登录状态")
            return data["data"]
        except WaterError:
            raise
        except Exception:
            raise WaterError("水务接口读取或解码失败") from None

    async def refresh(self):
        try:
            return await self._refresh_bills()
        except WaterAuthError:
            pass
        old_token = self.config["headers"].get("utoken")
        self.ctoken = None
        token = await self.request("renew", {
            "openid": self.config["headers"]["openid"],
            "channel": self.config["headers"]["channel"],
        })
        if not isinstance(token, dict) or not isinstance(token.get("token"), str) or not token["token"].strip():
            raise WaterAuthError("水务自动续期失败，请重新认证")
        self.config["headers"]["utoken"] = token["token"]
        try:
            return await self._refresh_bills()
        except BaseException:
            self.config["headers"]["utoken"] = old_token
            self.ctoken = None
            raise

    async def _refresh_bills(self):
        token = await self.request("token")
        if not isinstance(token, dict) or not token.get("token"):
            raise WaterAuthError("无法获取户号查询令牌，请重新认证")
        self.ctoken = token["token"]
        latest = await self.request("latest")
        history = await self.request("history")
        if not isinstance(latest, list) or not isinstance(history, list):
            raise WaterError("账单列表格式异常")
        bills = {}
        for row in history + latest:
            item = bill(row)
            if item:
                bills[item["month"]] = item
        partial = False
        for month in sorted(bills, reverse=True)[:60]:
            if month in self.details and month != max(bills):
                bills[month]["readings"] = self.details[month]
                continue
            try:
                rows = await self.request("detail", {**self.config["templates"]["detail"], "costdate": int(month.replace("-", ""))})
                detail = next((b for row in rows if (b := bill(row)) and b["month"] == month), None)
                if detail is None:
                    raise WaterError("缺少抄表明细")
                self.details[month] = detail["readings"]
                bills[month] = detail
            except WaterAuthError:
                raise
            except (WaterError, TypeError):
                partial = True
        return {"bills": [bills[m] for m in sorted(bills)], "partial": partial}
