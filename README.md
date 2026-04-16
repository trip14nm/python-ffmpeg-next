# python-ffmpeg-next

保存原始文件夹结构的批量视频转码脚本。

## 运行前准备

1. 确保已安装 `ffmpeg` 和 `ffprobe`，并且已添加到 `PATH`。
2. 将要处理的视频文件放入 `input` 目录（已自动创建）。
3. 如果需要自定义参数，可以修改 `config_example.yaml`，或者复制一份到 `config.yaml`。

## 默认配置文件

仓库内已包含 `config_example.yaml`，脚本会在找不到 `config.yaml` 时自动回退使用它。

## 运行方式

```powershell
python go.py
```

如果需要指定自定义路径：

```powershell
python go.py --config config_example.yaml --source input --target output
```

## 参数说明

- `--config`：指定配置文件路径，默认查找 `config.yaml`，若未找到则回退到 `config_example.yaml`。
- `--source`：输入目录，默认 `input`。
- `--target`：输出目录，默认 `output`。

## 说明

脚本会保留原始目录结构，转码后输出为 `*.mp4`，同名 `.ass` 字幕文件会尝试合并进视频。