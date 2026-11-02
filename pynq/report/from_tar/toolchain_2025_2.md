# Vivado / Vitis 2025.2 安装状态与官方参数

更新日期：2026-10-23。**官方安装器已下载、验签并解包；2025.2 尚未安装。** 图形安装器已退出。用户正在阅读 PPT，要求不弹窗；当前不运行任何安装器或界面，也不更改权限、UAC 或 Windows 安全设置。

当前实施顺序已调整为先用原始2019.2 bit/HWH在PYNQ验收，再按实际重建需要安装2025.2。现成Overlay的运行不要求先升级电脑上的Vivado；管理员权限仅阻碍新版工具安装，不阻碍继续准备或执行现有位流的板上验证。

## 当前文件与执行状态

| 项目 | 当前状态 |
| --- | --- |
| 安装器原文件 | `E:/Download/FPGAs_AdaptiveSoCs_Unified_SDI_2025.2_1114_2157_Win64.exe` |
| 安装器副本 | `D:/software/FPGAs_AdaptiveSoCs_Unified_SDI_2025.2_1114_2157_Win64.exe` |
| 文件大小 | 244,664,096 bytes |
| 本地 SHA-256 | `ddcea24a734b2727d152703c784bd822195a5898333cfc8c5041a92eadd6ea36` |
| Authenticode | `Valid`，签名者 `Xilinx, Inc.` |
| 已解包客户端 | `D:/software/amd_2025_2_installer`，通过 7-Zip 提取 |
| 批处理入口 | `D:/software/amd_2025_2_installer/bin/xsetup.bat` |
| 实际帮助调用 | `bin/xsetup.bat -h` 返回 `Administrative permissions are not available` |
| 当前进程管理员状态 | `current_process_is_admin = false` |
| 图形安装器 | 已退出，未开始安装 |
| 规划安装根目录 | `D:/software/AMDDesignTools` |
| 当前已知 Vivado | `D:/software/X/Vivado/2018.3/bin/vivado.bat`；不用于降级本工程 |
| 2025.2 综合、实现与板测 | 均未执行 |

上述 SHA-256 是本地实算值；文件已通过 Authenticode 验签。AMD 网页公布的 digest 尚未留存，因此未记录“本地 hash 与官方 digest 一致”的结论。官方 SFX 解包命令此前未生成目标目录，随后已用 7-Zip 得到上述客户端。

AMD 浏览器登录已由用户确认。批处理认证仍使用安装器自身的认证流程；报告不保存账号密码或 token。

## 适用版本与官方来源

目标器件为 `xc7z020clg484-2`。[UG973 2025.2 支持器件表](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Supported-Devices) 将 XC7Z020 列入 Vivado ML Standard Edition；[AMD 许可 FAQ](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/licensing-faq.html) 说明 2025.2 及更早版本的 ML Standard 不需要 FLEX 许可证。本工程选择 **2025.2 ML Standard**，附加收费 IP 的许可按实际 IP 单独核对。

[AMD 2025.2 官方下载页](https://www.amd.com/en/support/downloads/adaptive-socs-and-fpgas/development-tools/2025-2.html) 的基础发行版发布日期为 2025-11-20。已取得的文件对应 **Windows Self Extracting Web Installer**，官方标称 233.33 MB；[该文件的官方认证下载入口](https://account.amd.com/en/forms/downloads/xef.html?filename=FPGAs_AdaptiveSoCs_Unified_SDI_2025.2_1114_2157_Win64.exe) 使用 AMD 账号会话。

当前采用基础版 2025.2 Web Installer，未下载官方标称 95.68 GB 的 SFD 全量包，也未改用 2025.2.1 更新版。2026.1 的 BASIC 授权规则不适用于这里的 2025.2 选择。

[UG973 Verify the Digest](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Verify-the-Digest) 说明可核对 MD5、SHA1、SHA256、SHA512，并验证 digest 自身的 AMD 签名。现有本地检查对应以下只读命令：

```powershell
Get-FileHash -LiteralPath 'D:\software\FPGAs_AdaptiveSoCs_Unified_SDI_2025.2_1114_2157_Win64.exe' -Algorithm SHA256
Get-AuthenticodeSignature -LiteralPath 'D:\software\FPGAs_AdaptiveSoCs_Unified_SDI_2025.2_1114_2157_Win64.exe'
```

## 安装配置规划

配置以 [UG973 安装流程](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Run-the-Installation-File) 和实际 2025.2 组件菜单为准。尚未生成可确认的最终安装配置，也未开始组件下载与安装。

| 项目 | 规划选择 | 用途 |
| --- | --- | --- |
| 安装方式 | Download and Install Now | 按所选组件下载 |
| Vivado Edition | Vivado ML Standard | XC7Z020 综合、实现、时序分析和 bitstream |
| Vivado / HLS 集成依赖 | 保留必需组件 | 保持完整工具依赖；本工程继续使用原 HLS 算法与打包 RTL |
| Vitis Embedded Development | 选择 | 嵌入式平台与需要时的 FSBL/Bootgen |
| 器件 | Zynq-7000 | 覆盖 `xc7z020clg484-2` |
| 其他器件族 | 不选 | 缩减下载和安装占用 |
| Model Composer、PDM、DocNav、额外 IP cache | 暂不选 | 按实际需要后续补装 |
| Cable Drivers | 需要 JTAG 时安装 | 独立核对驱动安装条件 |

[UG973 Installer](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Installer) 说明，从 2025.1 起安装结构采用 `<安装根>/<版本>/Vivado`，Windows 默认根目录为 `C:/AMDDesignTools`；本项目规划改为 `D:/software/AMDDesignTools`。2025.2 HLS 集成于 Vitis，最终是否安装 Vitis Embedded Development 应以组件配置和实际版本输出确认，不能仅凭存在 Vitis 文件夹判断。

已有 2018.3 保留。原 2019.2 工程在副本中迁移，2025.2 构建入口见 `hardware_audit.md`；不修改原始 HLS 算法或原工程。

## 系统与空间要求

[UG1742 2025.2 Installation Requirements](https://docs.amd.com/r/2025.2-English/ug1742-vitis-release-notes/Installation-Requirements) 对 Embedded/HLS 列出 Windows 10 Pro/Enterprise 22H2、Windows 11 Enterprise 23H2/24H2，内存最低 32 GB、推荐 64 GB；磁盘条目中 Vitis Embedded Development 为 35 GB，Full Vitis 为 200 GB，并随组件和器件选择变化。

尚未完成当前机器的系统版本、内存和最终组件总空间验收。恢复安装时应记录 Summary 的 Download Size、Disk Space Required、下载缓存和最终安装目录，并预留解压、临时文件及工程构建空间。35 GB 条目不能直接作为 Vivado、HLS、嵌入式组件和器件文件的总占用。

## 官方 Windows 批处理命令参考

以下只保留参数说明，**当前不执行**。官方 Windows 批处理要求管理员命令环境；现有进程的管理员状态为 false，已经发生的 `-h` 调用在此条件处停止。当前不会重新打开图形安装器、弹出提权窗口或修改系统权限。

### 解包参数

[Extract Web Installer Batch Mode Client](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Extract-Web-Installer-Batch-Mode-Client) 的 Windows 参数为 `-y -gm2 -nr -InstallPath="<WI Client Dir>"`：

```powershell
& 'D:\software\FPGAs_AdaptiveSoCs_Unified_SDI_2025.2_1114_2157_Win64.exe' -y -gm2 -nr '-InstallPath=D:\software\amd_2025_2_installer'
```

客户端已经解包，无需为取得当前客户端再次执行该命令。`--keep --noexec --target` 属于官方 Linux `.bin` 示例。Windows 批处理调用解包目录的 **`bin/xsetup.bat`**。

### 配置生成

[Generate a Configuration File](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Generate-a-Configuration-File?contentId=hVSNtfXQKYiXeweLB8sL9g) 使用 `-b ConfigGen`：

```powershell
& 'D:\software\amd_2025_2_installer\bin\xsetup.bat' -b ConfigGen
```

按实际菜单选择产品与 Vivado ML Standard，保存完整配置路径；菜单数字以实际显示为准。配置中的 `1` 表示选择、`0` 表示不选。保留产品必需依赖，仅选择实际存在的 Zynq-7000 模块键；嵌入式需求须明确选择 Vitis Embedded Development。配置生成本身不等于安装。

### 批处理认证

[Acquire Authentication Token](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Acquire-Authentication-Token) 使用 `-b AuthTokenGen`，交互请求 AMD 账号并生成有效期 7 天的 token：

```powershell
& 'D:\software\amd_2025_2_installer\bin\xsetup.bat' -b AuthTokenGen
```

凭据和 token 不写入工程或报告。

### 下载与安装

[Web Installer Download and Install](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Web-Installer-Download-and-Install) 使用 `-b Install -a XilinxEULA,3rdPartyEULA -c <配置文件>`：

```powershell
& 'D:\software\amd_2025_2_installer\bin\xsetup.bat' -b Install -a 'XilinxEULA,3rdPartyEULA' -c 'E:\work\FPGA\Qian\pynq_port\build\install_2025_2_config.txt'
```

该配置路径是预定示例，最终以实际生成并核对的配置为准；`-a` 表示接受指定许可。上述安装命令尚未执行。

[Running the Installer](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Running-the-Installer) 还列出等价长参数 `--batch Install --agree XilinxEULA,3rdPartyEULA --config <配置文件>`，帮助参数为 `-h` / `--help`。只给 edition 和 location 会采用默认组件，精简器件应使用已核对的配置文件。

## 后续完成条件

恢复安装后，以安装日志和实际 Vivado/Vitis 2025.2 版本输出确认工具可用；随后运行新工程的 IP 升级、综合、实现与导出，保存资源和时序报告，并进行 PYNQ 板上比对。目前完成到安装器下载、有效签名核验和客户端解包；不提前记为安装完成、编译通过或板测通过。
