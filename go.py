import os
import shutil
import yaml
import subprocess

# 默认的源文件夹路径和目标文件夹路径
source_folder = 'input'
target_folder = 'output'

# 读取配置文件
with open('config.yaml', encoding='utf-8') as config_file:
    config = yaml.safe_load(config_file)

video_extensions = config['video_extensions']
ffmpeg_params = config['encode_params']
input_params = config['decode_params']
ignore_files = config['ignore_files']

# 分辨率阈值和长宽比容差
max_pixels = config['resolution_threshold']
aspect_ratio_tolerance = 0.1


def get_video_resolution(video_path):
    """获取视频分辨率"""
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        width, height = map(int, result.stdout.strip().split('x'))
        return width, height
    return None, None


def check_existing_video(target_folder, video_name, video_ext):
    """检查目标文件夹中是否存在完整的目标视频文件"""
    expected_filename = f"{video_name}{video_ext}"
    for root, _, files in os.walk(target_folder):
        if expected_filename in files:
            return True
    return False


def process_video(video_path, target_folder):
    # 处理路径结构
    relative_path = os.path.relpath(os.path.dirname(video_path), source_folder)
    target_subfolder = os.path.join(target_folder, relative_path)
    os.makedirs(target_subfolder, exist_ok=True)

    # 提取视频信息
    video_name, video_ext = os.path.splitext(os.path.basename(video_path))
    
    # 检查字幕文件
    video_dir = os.path.dirname(video_path)
    subs_path = os.path.join(video_dir, f"{video_name}.ass")
    subs_exists = os.path.isfile(subs_path)

    # 跳过已存在文件
    if check_existing_video(target_subfolder, video_name, '.mp4'):
        print(f"跳过已存在文件: {video_path}")
        return

    # 获取分辨率
    width, height = get_video_resolution(video_path)
    if not width or not height:
        print(f"无法获取分辨率: {video_path}")
        return

    # 分辨率处理逻辑
    pixels = width * height
    aspect_ratio = width / height
    reverse_ratio = height / width
    scale_filter = None

    if pixels > max_pixels:
        if abs(aspect_ratio - 16/9) < aspect_ratio_tolerance:
            scale_filter = "scale=1920:1080"
            print(f"16:9 超限视频: {width}x{height} -> 1920x1080")
        elif abs(reverse_ratio - 16/9) < aspect_ratio_tolerance:
            scale_filter = "scale=1080:1920"
            print(f"9:16 超限视频: {width}x{height} -> 1080x1920")
        else:
            scale_factor = (max_pixels / pixels) ** 0.5
            new_w = int(width * scale_factor)
            new_h = int(height * scale_factor)
            scale_filter = f"scale={new_w}:{new_h}"
            print(f"自适配缩放: {width}x{height} -> {new_w}x{new_h}")

    # 构建滤镜链
    vf_components = []
    if scale_filter:
        vf_components.append(scale_filter)
    if subs_exists:
        # ffmpeg 字幕路径转义
        subs_path_ffmpeg = subs_path.replace('\\', '/').replace(':', '\\:')
        vf_components.append(f"subtitles='{subs_path_ffmpeg}'")
        print(f"检测到字幕文件: {subs_path}")

    # 构建转码命令
    temp_output = os.path.join(target_subfolder, f"{video_name}_part.mp4")
    ffmpeg_cmd = ['ffmpeg']
    
    if input_params:
        ffmpeg_cmd.extend(input_params.split())
    
    ffmpeg_cmd.extend(['-i', video_path])
    
    if vf_components:
        ffmpeg_cmd.extend(['-vf', ','.join(vf_components)])
    
    ffmpeg_cmd.extend(ffmpeg_params.split())
    ffmpeg_cmd.extend(['-y', temp_output])

    # 执行转码
    print("执行命令:", ' '.join(ffmpeg_cmd))
    subprocess.run(ffmpeg_cmd, check=True)

    # 重命名最终文件
    final_output = os.path.join(target_subfolder, f"{video_name}.mp4")
    os.rename(temp_output, final_output)
    print(f"转码完成: {final_output}\n")

# 主处理流程
if __name__ == '__main__':
    default_source = os.path.join(os.getcwd(), source_folder)
    used_subtitles = set()  # 记录已被内嵌的视频字幕文件

    for root, dirs, files in os.walk(default_source):
        for file in files:
            path = os.path.join(root, file)
            # 视频文件处理
            if any(file.endswith(ext) for ext in video_extensions):
                process_video(path, target_folder)
                # 记录已用字幕
                video_name, _ = os.path.splitext(file)
                subs_path = os.path.join(root, f"{video_name}.ass")
                if os.path.isfile(subs_path):
                    used_subtitles.add(os.path.abspath(subs_path))
            else:
                # 跳过忽略文件
                if file in ignore_files:
                    continue
                # 跳过已被合并的字幕文件
                if os.path.abspath(path) in used_subtitles:
                    continue
                # 复制其他文件
                rel_path = os.path.relpath(root, default_source)
                target_dir = os.path.join(target_folder, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(path, target_dir)

    print("所有处理已完成！")
