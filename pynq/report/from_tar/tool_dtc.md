# Windows dtc 与离线 Overlay 工具

日期：2026-10-23。工具仅在工作区解包和编译；未安装 MSYS2，未改系统目录或持久环境变量，未启动图形界面或管理员安装。真实 AC820 DTB 的离线合并已通过，但尚未应用到启动镜像或板卡。

## 当前可用入口

| 用途 | 工作区路径 | 实际版本 |
| --- | --- | --- |
| 编译 DTS | `build/work/dtc/bin/dtc.exe` | `Version: DTC 1.8.1` |
| Windows 二进制安全 Overlay 合并 | `build/work/dtc/bin/fdtoverlay_binary.exe` | 自有前端 1.0，调用原版 libfdt 1.8.1 |
| 可发布、可重编译的前端源码 | `build/native_fdtoverlay.c` | SHA-256 见下表 |

路径以 `E:/work/FPGA/Qian/pynq_port` 为根。**Windows 下请使用 `fdtoverlay_binary.exe`，不要使用同目录中原包的 `fdtoverlay.exe` 或 `fdtget.exe` 读取真实二进制 DTB。** 原包保留用于来源核验和问题复现，不代表它的文件 I/O 在本机正确。

## 官方来源与下载校验

上游是 [Device Tree Compiler / libfdt](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/)。Windows 原生包来自 MSYS2 官方 UCRT64 仓库，并按官方包页面公布的 SHA-256 校验：

| 官方包 | 大小 | 官方公布且本地匹配的 SHA-256 |
| --- | ---: | --- |
| [dtc 1.8.1-1](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-dtc) | 405065 bytes | `0f3c4df43133b99e040f7d42666e36e50c9aea2f59a494e0aad3b475f3fdd32d` |
| [libyaml 0.2.5-2](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-libyaml) | 87127 bytes | `bf4c28a3a92a46db3c809b0789aef731ae9a0c4283db368c7e8624550fed07f3` |

实际下载地址为：

- [MSYS2 官方 dtc 包](https://repo.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-dtc-1.8.1-1-any.pkg.tar.zst)
- [MSYS2 官方 libyaml 包](https://repo.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-libyaml-0.2.5-2-any.pkg.tar.zst)

官方 geo mirror 的一次连接出现 TLS EOF，实际改用同属 MSYS2 的 `repo.msys2.org` 源站，并以上表校验和确认文件内容。验证边界为 HTTPS 官方元数据加 SHA-256 匹配；**未额外进行 detached PGP 签名验证**，不宣称完成了 pacman 信任链验签。

原压缩包留于 `build/work/dtc/downloads/`，使用现有 `E:/software/7-Zip/7z.exe` 依次解开 Zstandard 和 TAR；完整内容分别保留于 `packages/dtc/` 与 `packages/libyaml/`。许可证和包元数据随原包保留。工具目录中不需要 MSYS 运行时。

## 真实输入暴露的原包 I/O 问题

[上游 v1.8.1 util.c](https://raw.githubusercontent.com/dgibson/dtc/v1.8.1/util.c) 的 `utilfdt_read_err` 使用 `open(filename, O_RDONLY)`，未指定 Windows 二进制模式；写函数同样未指定二进制模式。Windows 文本模式会处理 DOS EOF 字节 `0x1A` 和 CRLF，而 DTB 是任意二进制数据。该读函数返回的长度还是缓冲容量，因此错误信息中的 4096 不是实际文件长度。

真实基底 `build/work/board_image/system.dtb` 为 **19123 bytes**，头部 totalsize 同为 19123，首个 `0x1A` 位于偏移 3059。原包 `fdtoverlay.exe` 实际复现：

```text
Base blob is incomplete (4096 / 19123 bytes read)
```

原先小型合成烟测未覆盖该字节，不能证明真实 DTB 可读。问题出在 Windows 前端 I/O，不是 FIT 提取不足；没有截断、填充或改写原 DTB 来规避错误。

## 二进制安全前端

`build/native_fdtoverlay.c` 使用显式 `rb` / `wb` 完整读写文件，并调用官方 DLL 提供的 `fdt_check_full`、`fdt_open_into`、`fdt_overlay_apply`、`fdt_pack`。**未修改 libfdt 实现。** 每次合并都使用基底和 Overlay 的内存副本，失败后从未破坏的副本重试；输出拒绝使用与输入相同的规范化路径。

内存容量按 libfdt 要求增长，最终通过 `fdt_pack` 压紧输出；这不是补齐输入或截掉输入错误。输入完整性在应用前由文件读取长度和 `fdt_check_full` 检查，输出再次经过完整检查。

本机编译器为 `D:/environment/mingw64/bin/gcc.exe`，版本 `15.1.0`，目标 `x86_64-ucrt-posix-seh`。在 `pynq_port` 目录运行的精确命令为：

```powershell
& 'D:/environment/mingw64/bin/gcc.exe' -std=c11 -O2 -Wall -Wextra -Werror '-Wl,--no-insert-timestamp' '-Ibuild/work/dtc/packages/dtc/ucrt64/include' 'build/native_fdtoverlay.c' '-Lbuild/work/dtc/packages/dtc/ucrt64/lib' -lfdt -o 'build/work/dtc/bin/fdtoverlay_binary.exe'
```

头文件及 import library 来自已校验的 dtc 包。运行时将同一包的 `libfdt-1.dll` 放在 EXE 同目录；`dtc.exe` 还需将已校验 libyaml 包中的 `libyaml-0-2.dll` 放在该目录。其余导入为 Windows Kernel32/UCRT 系统组件，已用现有 `objdump.exe` 检查依赖；未配置系统 PATH。

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `build/native_fdtoverlay.c` | 5831 | `41c3f7bafd047d45c0ece9b22c847304c30400dd33b08634081d97e05c5eddd1` |
| `bin/fdtoverlay_binary.exe` | 68580 | `9f3b44e5fd30cb47705f07f11efbe92d3b5dd99773affe6fb009bd716562be8d` |
| `bin/libfdt-1.dll` | 213430 | `f5cfc89c258fee56229290d331c29e98ae230312ff063bfa0a5377750c6cdda5` |
| `packages/dtc/ucrt64/lib/libfdt.dll.a` | 54132 | `9ab21d2d5d43a1de53693a6fb01c2c0c8bb932a6d182e58af36dab180d523206` |
| `bin/libyaml-0-2.dll` | 155273 | `1942ec5a43f1b22dd651283ab2b00efe8ccee907d4bccfa86fd5ba95b0985aba` |

除首项外，上表相对 `build/work/dtc/`。构建使用 `--no-insert-timestamp` 避免 PE 链接时间戳变化，但换编译器或参数仍可能改变 EXE 哈希。`sources_and_frontend.json` 保存来源、包哈希、运行依赖及复验信息。

## 真实 AC820 基底验证

实际验证使用主流程从 FIT 导出的原基底及主流程已用真实 dtc 编译的 `board/linux/leaf_peripherals.dtbo`；不修改 DTS 或原始 DTB。前端调用：

```powershell
& 'build/work/dtc/bin/fdtoverlay_binary.exe' -i 'build/work/board_image/system.dtb' -o 'build/work/dtc/real_validation/system_leaf.dtb' 'board/linux/leaf_peripherals.dtbo'
```

实际返回码为 0，输出：

```text
Applied 1 overlay(s); read 19123 complete base bytes, wrote 15557 binary bytes
```

- 原基底 SHA-256：`28d656e6da69a652484d29210fe99ef990a105125d9d834666ca69736a427f2f`。
- 合并结果 SHA-256：`8e154dbf9659ac0ad81be59381a2e56dbf25babbc57b21ab0cf5133ef02af858`。
- 合并结果 magic 正确、头部 totalsize 等于实际 15557 bytes，并通过 libfdt 完整检查。
- 原基底、Overlay、DTS 前后哈希未变；尝试将输出设为原基底路径被拒绝。
- 从发布用 C 源重新编译前端后，再次对真实输入合并，结果与首次输出逐字节相同。

日志位于 `build/work/dtc/real_validation/validation.json`。节点语义和全树差异由主流程独立比对；本记录证明真实文件能够完整读取和离线应用 Overlay，不代替内核驱动、启动期加载或板上 I2C/GPIO 验证。

`build/work` 工具目录不进入常规发布包。发布包保留 C 源和本报告，可按官方包来源、哈希和上述命令在独立工作目录重建工具；不得只依赖本机 EXE 路径完成复现。
