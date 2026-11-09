# OLED 中文界面字形

`main/oled_font_zh.h` 是 **Discora UI subset**：从 Noto Sans CJK SC Regular 2.004 转为 16×16 单色点阵，仅包含固定中文界面的用字，不支持任意歌曲名称。它作为常量直接编译进 ESP32-S3 固件，不需要第三方运行时字体库。

- 上游：[Noto CJK](https://github.com/notofonts/noto-cjk)，[源字体](https://github.com/notofonts/noto-cjk/blob/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf)。
- Copyright 2014–2021 Adobe (http://www.adobe.com/)。
- 许可：[SIL Open Font License 1.1](OFL-NotoSansCJK.txt)，适用于派生字形，不改变项目其它代码许可。
- 输入文件 SHA-256：`2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b`。生成器校验摘要，防止上游同路径更新后静默改变字形。
- 生成环境：Pillow 13.0.0 / FreeType；仅在修改字形时需要。普通固件构建不需要 Python 字体依赖或原字体。

在已安装 Pillow 的主机 Python 环境中，从仓库根目录运行：

```sh
python3 firmware/tools/generate_oled_font.py /path/to/NotoSansCJKsc-Regular.otf firmware/main/oled_font_zh.h
```

字体以 16 px、基线 y=14 渲染，灰度阈值 96 转为 1 bit；每字 16 个 `uint16_t`，最高位在左。生成头部保留来源、版权与许可标识。发布字形时须随附许可文件。
