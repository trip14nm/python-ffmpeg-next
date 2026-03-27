import os
import shutil
import yaml
import subprocess
import json
import logging
from datetime import datetime

# 默认的源文件夹路径和目标文件夹路径
source_folder = 'input'
target_folder = 'output'

# 读取配置文件
with open('config.yaml', encoding='utf-8') as config_file:
    config = yaml.safe_load(config_file)

video_extensions = [ext.lower() for ext in config['video_extensions']]  # normalize to lowercase

# encode/decode params 支持列表和字符串两种格式
def parse_params(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    return value.split()

ffmpeg_params = parse_params(config['encode_params'])
input_params = parse_params(config['decode_params'])

ignore_files = [f.lower() for f in config['ignore_files']]  # normalize to lowercase

# 分辨率阈值
max_pixels = config['resolution_threshold']

# 日志配置
os.makedirs('logs', exist_ok=True)
log_filename = os.path.join('logs', datetime.now().strftime("process_%Y%m%d_%H%M%S.log"))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger()

# 检测 ffmpeg 和 ffprobe 是否可用
for tool in ("ffmpeg", "ffprobe"):
    if not shutil.which(tool):
        log.error(f"未找到 {tool}，请确认已安装并添加到 PATH 后重试")
        raise SystemExit(1)


def get_video_resolution(video_path):
    """使用 ffprobe 获取视频分辨率 (JSON 模式)"""
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0 and result.stdout:
        try:
            data = json.loads(result.stdout)
            if 'streams' in data and data['streams']:
                stream = data['streams'][0]
                width = stream.get('width')
                height = stream.get('height')
                if width is not None and height is not None:
                    return int(width), int(height)
        except (json.JSONDecodeError, IndexError, ValueError) as e:
            log.error(f"解析 ffprobe JSON 输出失败: {e}")

    return None, None


def check_existing_video(target_subfolder, video_name):
    """检查对应子目录中是否已存在目标视频文件"""
    return os.path.exists(os.path.join(target_subfolder, f"{video_name}.mp4"))


def escape_subtitle_path(path):
    """
    转义 ffmpeg subtitles filter 路径中的特殊字符。
    ffmpeg vf 字符串中需要转义的字符：\ : ' [ ] , ;
    """
    path = path.replace('\\', '/')
    for ch in (':', "'", '[', ']', ',', ';'):
        path = path.replace(ch, f'\\{ch}')
    return path


def find_subtitle(video_dir, video_name):
    """大小写不敏感地查找匹配的 .ass 字幕文件"""
    for f in os.listdir(video_dir):
        name, ext = os.path.splitext(f)
        if name.lower() == video_name.lower() and ext.lower() == '.ass':
            return os.path.join(video_dir, f)
    return None


def collect_subtitles(source_folder):
    """预扫描所有视频对应的字幕文件，返回绝对路径集合"""
    subtitle_paths = set()
    for root, _, files in os.walk(source_folder):
        for file in files:
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_name, _ = os.path.splitext(file)
                subs_path = find_subtitle(root, video_name)
                if subs_path:
                    subtitle_paths.add(os.path.abspath(subs_path))
    return subtitle_paths


def process_video(video_path, target_folder):
    # 处理路径结构
    relative_path = os.path.relpath(os.path.dirname(video_path), source_folder)
    target_subfolder = os.path.join(target_folder, relative_path)
    os.makedirs(target_subfolder, exist_ok=True)

    # 提取视频信息
    video_name, video_ext = os.path.splitext(os.path.basename(video_path))

    # 检查字幕文件 (case-insensitive)
    video_dir = os.path.dirname(video_path)
    subs_path = find_subtitle(video_dir, video_name)
    subs_exists = subs_path is not None

    # 跳过已存在文件
    if check_existing_video(target_subfolder, video_name):
        log.info(f"跳过已存在文件: {video_path}")
        return

    # 获取分辨率
    width, height = get_video_resolution(video_path)
    if not width or not height:
        log.warning(f"无法获取分辨率: {video_path}")
        return

    # 分辨率处理逻辑
    pixels = width * height
    scale_filter = None

    if pixels > max_pixels:
        # 用像素总量开方得到等比缩放系数，round 后强制对齐到 2 的倍数
        # （yuv420p 要求宽高均为偶数，直接用 int() 截断会导致标准分辨率差几个像素）
        # 例：3840x2160 -> scale_factor=0.5 -> new_w=1920, new_h=1080，完全精确
        scale_factor = (max_pixels / pixels) ** 0.5
        new_w = round(width * scale_factor / 2) * 2
        new_h = round(height * scale_factor / 2) * 2
        scale_filter = f"scale={new_w}:{new_h}"
        log.info(f"缩放: {width}x{height} -> {new_w}x{new_h}")

    # 构建滤镜链
    vf_components = []
    if scale_filter:
        vf_components.append(scale_filter)
    if subs_exists:
        escaped_path = escape_subtitle_path(subs_path)
        vf_components.append(f"subtitles='{escaped_path}'")
        log.info(f"检测到字幕文件: {subs_path}")

    # 构建转码命令
    temp_output = os.path.join(target_subfolder, f"{video_name}_part.mp4")
    ffmpeg_cmd = ['ffmpeg']

    if input_params:
        ffmpeg_cmd.extend(input_params)

    ffmpeg_cmd.extend(['-i', video_path])

    if vf_components:
        ffmpeg_cmd.extend(['-vf', ','.join(vf_components)])

    ffmpeg_cmd.extend(ffmpeg_params)
    ffmpeg_cmd.extend(['-y', temp_output])

    # 执行转码
    log.info("执行命令: " + ' '.join(ffmpeg_cmd))
    subprocess.run(ffmpeg_cmd, check=True)

    # 重命名最终文件
    final_output = os.path.join(target_subfolder, f"{video_name}.mp4")
    os.rename(temp_output, final_output)
    log.info(f"转码完成: {final_output}\n")


# 主处理流程
if __name__ == '__main__':
    default_source = os.path.join(os.getcwd(), source_folder)

    log.info("=" * 60)
    log.info("开始处理")
    log.info("=" * 60)

    # 预扫描所有将被合并的字幕文件
    used_subtitles = collect_subtitles(default_source)

    for root, dirs, files in os.walk(default_source):
        for file in files:
            path = os.path.join(root, file)
            # 视频文件处理 (case-insensitive extension check)
            if any(file.lower().endswith(ext) for ext in video_extensions):
                process_video(path, target_folder)
            else:
                # 跳过忽略文件 (case-insensitive)
                if file.lower() in ignore_files:
                    continue
                # 跳过已被合并的字幕文件
                if os.path.abspath(path) in used_subtitles:
                    continue
                # 复制其他文件
                rel_path = os.path.relpath(root, default_source)
                target_dir = os.path.join(target_folder, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(path, target_dir)
                log.info(f"复制文件: {file} -> {target_dir}")

    log.info("=" * 60)
    log.info("所有处理已完成！")
    log.info(f"日志已保存至: {log_filename}")
    log.info("=" * 60)
