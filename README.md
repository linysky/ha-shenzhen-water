# 深圳水务 · Home Assistant 自定义集成

把深圳水务账户数据接入 Home Assistant。非官方社区集成，不隶属于供水/供电/燃气公司；接口可能变化，请以官方账单为准。

## 安装

**HA 2026.11+ 内置市场（Marketplace）**：设置 → 市场 → 右上角「从链接添加」→ 粘贴 `https://github.com/linysky/ha-shenzhen-water` → 安装。首次使用需连接 GitHub（设备登录，只读公开信息），并接受市场的社区项目风险提示。旧版 HACS 用「自定义仓库」，填同一 URL、类型选 Integration。

**手动安装**：把 `custom_components/shenzhen_water/` 复制到 HA 的 `/config/custom_components/`（Docker 对应自己的持久化挂载目录，注意目录层级不要多嵌套一层），重启 HA，再到「设置 → 设备与服务 → 添加集成」搜索「深圳水务」。

## 配置与凭据获取

见 [docs/water.md](docs/water.md) 与 [docs/security.md](docs/security.md)。凭据只能从本人已授权的官方小程序/App 获取；本仓库不含任何账户凭据或账单数据。

## 注意

- `unknown`/`unavailable` 不等于 0，不要用补零掩盖认证或网络故障；月度账单不是连续累计电表读数，不要配成 HA Energy 的累计传感器。
- 凭据（token / CodeId / 会话 JSON）明文存于 HA `.storage`，请勿公开配置备份；分享日志前必须脱敏。
- domain `shenzhen_water` 与 `CelerPi/HA-Shenzhen-Water-Integration` 相同；Home Assistant 市场不允许两个仓库安装同一 domain，二者只能选一个。
- 本仓库是 https://github.com/mintisan/home-assistant-shenzhen-utilities 集合仓库的单集成拆分，**包含该仓库的补丁**；上游单集成版本不一定含这些补丁。完整来源与修改范围见 [NOTICE.md](NOTICE.md)，许可证：MIT。
