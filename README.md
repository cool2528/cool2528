# 你好，我是 cool

我有 9 年以上 C++ 开发经验，主要做 **跨平台桌面应用、网络下载和高并发服务端**。也做 **Windows 二进制分析**，熟悉 x86 汇编、PE 文件格式和运行时调试。

## GDownload

我用 **C++20 和 Qt 6** 开发的下载管理器，支持 Windows、macOS 和 Linux。它通过 aria2 下载 HTTP(S)、FTP 和 BitTorrent 资源，也集成了自研的 eD2k 引擎，支持 Kad 搜索、多源下载和断点续传。

[**下载最新版**](https://github.com/cool2528/GDownload/releases/latest) · [查看源码](https://github.com/cool2528/GDownload) · [项目官网](https://gdownload.uk/)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/cool2528/GDownload/main/screenshot/screenshot-2.png">
  <img src="https://raw.githubusercontent.com/cool2528/GDownload/main/screenshot/screenshot-1.png" alt="GDownload 下载界面，显示任务进度、速度和连接数" width="660">
</picture>

### 引擎与扩展

- [**ed2k-engine-cpp**](https://github.com/cool2528/ed2k-engine-cpp) · 基于 Boost.Asio 协程的 C++20 eDonkey/eMule 协议引擎。对照 aMule 源码逐字节核验协议格式，并用 aMule 2.3.3 做[互操作测试](https://github.com/cool2528/ed2k-engine-cpp#live-tests)。
- [**gd-browser-extension**](https://github.com/cool2528/gd-browser-extension) · 用 TypeScript 编写的 Chrome、Edge 和 Firefox 扩展，可捕获网页资源链接并批量发送到 GDownload。
- [**gdownload-plugin-registry**](https://github.com/cool2528/gdownload-plugin-registry) · GDownload 插件市场的注册表，维护 JavaScript 插件索引和签名版本。

## 其他开源项目

- [**tarswire**](https://github.com/cool2528/tarswire) · C++ Tars/JCE 编解码与查询库，附带 CLI，可将十六进制数据解析为 JSON。
- [**linguist-ai**](https://github.com/cool2528/linguist-ai) · 用 Python 自动翻译 Qt `.ts` 文件，支持多种翻译服务，并保留占位符和格式。
- [**VideoHardwareEncoding**](https://github.com/cool2528/VideoHardwareEncoding) · 使用 FFmpeg 实现硬件编码录屏，涉及 NVIDIA、AMD 和 Intel GPU。
- [**minizip**](https://github.com/cool2528/minizip) · 基于 zlib / minizip 的文件和目录打包、解包封装。

## 已归档项目

- [**baiduCDP**](https://github.com/cool2528/baiduCDP) · 早期的 Windows 百度网盘下载工具。
- [**aria2cengine**](https://github.com/cool2528/aria2cengine) · 早期基于 aria2 的下载引擎实践。

[浏览全部公开仓库](https://github.com/cool2528?tab=repositories)

<details>
<summary>GitHub 统计与贡献图</summary>

<p>
  <img src="https://raw.githubusercontent.com/cool2528/cool2528/output/stats-card.svg" alt="GitHub 关注人数、原创公开仓库数和这些仓库的 Star 与 Fork 总数" width="375">
  <img src="https://raw.githubusercontent.com/cool2528/cool2528/output/top-langs.svg" alt="原创公开仓库的编程语言字节占比" width="281">
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/cool2528/cool2528/output/github-snake-dark.svg">
  <img src="https://raw.githubusercontent.com/cool2528/cool2528/output/github-snake.svg" alt="GitHub 贡献日历贪吃蛇动画">
</picture>

</details>
