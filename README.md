# Moj A1 简体中文汉化（非官方）

一个仅作用于 Android 应用 **Moj A1**（包名 `hr.infinum.mojvip`）的离线 LSPosed 汉化模块。

> **非官方项目。** 本项目与 A1 Hrvatska d.o.o.、Infinum 或 Moj A1 官方没有隶属、授权、认可或合作关系。本仓库不包含、修改或分发 Moj A1 官方 APK。

## 当前版本

- 模块：`MojA1Zh 0.2.1-p1`（versionCode `4`）
- 目标应用：Moj A1 `7.0.1`（versionCode `7010000`）
- 目标语言：简体中文
- 运行环境：Android 24+、LSPosed API 93+

未知 Moj A1 版本会自动停用翻译并保留原文，避免因应用升级导致错误替换。

## 特点

- 完全离线，不调用在线翻译服务；
- 模块不申请联网权限；
- 不修改 Moj A1 APK、签名、请求、响应或账户数据；
- 不绕过登录、认证、支付、套餐限制或完整性检查；
- `EditText` 用户输入永不替换；
- 服务端文本必须同时匹配完整原文、Activity 和 view ID；
- 金额、手机号、日期、EUR、GB/MB、分钟数和套餐价格保持原样；
- 日志只记录规则 ID，不记录账户文本。

## 已覆盖页面

- 登录前入口和登录页面；
- 已登录首页、趋势、个人资料和商城；
- 设置、通知、充值码和使用指南；
- 套餐说明、套餐选择说明和套餐列表；
- Moj A1 申请页；
- 首页及商城的流量加餐横向轮播。

外部 `www.a1.hr` WebView、法律正文及插图中烘焙的文字不在当前覆盖范围内。

## 安装

1. 确认设备已安装并启用 LSPosed；
2. 从 [Releases](../../releases) 下载签名 APK；
3. 安装 APK；
4. 在 LSPosed 中启用模块，作用域只选择 **Moj A1**；
5. 将系统语言设为简体中文；
6. 强制停止并重新打开 Moj A1。

请自行从官方渠道安装 Moj A1。本项目不提供官方应用安装包。

## 构建

翻译数据生成：

```powershell
python MojA1Zh/tools/generate_translations.py
```

模块使用 Termux 中的 ECJ、DX 和 AAPT 构建。详细步骤见 [docs/BUILD.md](docs/BUILD.md)。

## 隐私与安全

参见：

- [PRIVACY.md](PRIVACY.md)
- [SECURITY.md](SECURITY.md)
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md)

提交问题时，请勿上传手机号、余额、邮箱、账户截图、UIAutomator XML、日志数据库或其他账户资料。

## 法律声明

Moj A1、A1 及相关名称、商标、图形和官方文案归各自权利人所有。仓库中的克罗地亚语文本仅作为实现兼容性所需的匹配标识；本项目许可证只覆盖项目作者和贡献者有权许可的代码与原创中文翻译。详见 [NOTICE.md](NOTICE.md)。

## 许可证

本项目以 [GNU General Public License v3.0](LICENSE) 发布。

