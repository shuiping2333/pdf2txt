# pdf2txt

把扫描版 PDF 按页识别成 Markdown 或纯文本。页面用 PyMuPDF 渲染，文字用 RapidOCR 识别简体中文和英文，在 CPU 上运行。

写出前会去掉页眉和单独成行的 `>`，并把同一段里被换行拆开的句子接上。每一页以 `## 第 n 页` 开头，短标题写成 `###`。

## 别人下载后怎么用

需要先安装 [Python 3.12 或更新版本](https://www.python.org/downloads/)，安装时勾选 **Add python.exe to PATH**。

下载本仓库后，把要转的 PDF 放在解压出来的目录里（不要放进子目录），双击对应的批处理。第一次运行会自动创建虚拟环境并安装依赖，需要联网，可能要十几分钟。装好之后再双击就直接开始转换。

## 双击转换

把要转的 PDF 放在本目录（不要放进子目录），双击对应的批处理。

| 文件 | 结果 |
|---|---|
| `pdf2md.bat` | 同名 `.md` |
| `pdf2txt.bat` | 同名 `.txt` |

脚本按文件名排序，转换第一个 PDF。窗口会留着显示进度，结束后按任意键关闭。

某页如果没有检测到文字，会提示 `The text detection result is empty`，然后继续后面的页。这种页多半是空白页或整页插图。

## 命令行

在本目录执行：

```powershell
.\.venv\Scripts\python.exe pdf2txt.py "书.pdf" -o "书.md"
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--format md` | 输出 Markdown。`-o` 以 `.md` 结尾时也会自动用 Markdown |
| `--format txt` | 输出纯文本 |
| `--start 1 --end 10` | 只转这一段页码，页码从 1 开始 |
| `--dpi 300` | 渲染分辨率，默认 200。字模糊时可调高，速度会变慢 |
| `--first` | 转换当前目录里按文件名排序的第一个 PDF |

不写 `-o` 时，结果文件与 PDF 同名，扩展名按格式变成 `.md` 或 `.txt`。

## 环境

本目录已有 `.venv`。换机器或虚拟环境丢失时，用 Python 3.12 重建：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
