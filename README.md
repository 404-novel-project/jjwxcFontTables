# 晋江自定义字体破解辅助工具

## 使用方法

```
python main.py --help
usage: main.py [-h] [--all] [--new] [--bundle] [--rehtml] [--font FONT]

晋江自定义字体破解辅助工具。

options:
  -h, --help   show this help message and exit
  --all        匹配所有fonts目录下的woff2字体文件。
  --new        匹配fonts目录下新woff2字体。
  --bundle     打包tables目录下所有json文件。
  --rehtml     重新生成HTML文件
  --font FONT  匹配指字名称字体文件。 例始：--font jjwxcfont_00gxm
```

## 自定义字体对照表

晋江自定义字体对照表位于 `tables` 目录，其中json文件为字体对照表，html文件用于方便校对查看。

如需打包版本，请切换至 gh-pages 分支。`bundle.json` 即为打包后版本。

在线查看晋江自定义字体对照表：https://404-novel-project.github.io/jjwxcFontTables/

## 实现思路

参见博文《[实例详解自定义字体反爬的对抗](https://blog.bgme.me/posts/shi-li-xiang-jie-zi-ding-yi-zi-ti-fan-pa-de-dui-kang/)》