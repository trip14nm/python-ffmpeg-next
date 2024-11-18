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

# 读取配置文件中的分辨率阈值
max_pixels = config['resolution_threshold']  # 从配置文件中获取最大像素值

def get_video_resolution(video_path):
    """获取视频分辨率"""
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    resolution = result.stdout.strip()
    if resolution:
        width, height = map(int, resolution.split('x'))
        return width, height
    return None, None

def check_existing_video(target_folder, video_name, video_ext):
    # 检查目标文件夹中是否存在同名的完整视频文件
    for root, _, files in os.walk(target_folder):
        for file in files:
            if file.startswith(video_name) and file.endswith(video_ext) and not file.endswith('_part' + video_ext):
                return True
    return False

def process_video(video_path, target_folder):
    # 获取目标文件夹的相对路径
    relative_path = os.path.relpath(os.path.dirname(video_path), source_folder)
    # 拼接目标文件夹中的相对路径
    target_subfolder = os.path.join(target_folder, relative_path)
    
    # 如果目标文件夹不存在，则创建
    os.makedirs(target_subfolder, exist_ok=True)
    
    # 获取视频文件名和扩展名
    video_name, video_ext = os.path.splitext(os.path.basename(video_path))
    
    # 检查目标路径是否已经存在完整视频文件
    if check_existing_video(target_subfolder, video_name, video_ext):
        print(f"已存在完整视频文件，跳过转码：{video_path}")
        return
    
    # 获取视频分辨率
    video_width, video_height = get_video_resolution(video_path)
    if video_width and video_height:
        print(f"视频分辨率：{video_width}x{video_height}")
    
    # 计算视频的像素总数
    video_pixels = video_width * video_height
    
    # 如果视频像素总数大于目标像素值，则按比例缩放
    if video_pixels > max_pixels:
        # 计算缩放比例，使得新的像素总数小于或等于最大像素值
        scale_factor = (max_pixels / video_pixels) ** 0.5  # 按比例缩放，保持长宽比
        new_width = int(video_width * scale_factor)
        new_height = int(video_height * scale_factor)
        print(f"视频像素总数大于 {max_pixels}，按比例缩放至 {new_width}x{new_height}")
        
        # 使用 ffmpeg 的 scale 参数进行缩放
        scale_filter = f"scale={new_width}:{new_height}"
    else:
        # 如果视频像素总数小于等于目标值，不做更改
        scale_filter = None
    
    # 定义转码后的文件名和路径，加上 .part 后缀
    target_video_name = video_name + '_part' + '.mp4'
    target_video_path = os.path.join(target_subfolder, target_video_name)
    
    # 构建ffmpeg命令
    cmd = f'ffmpeg {input_params} -i "{video_path}"'
    if scale_filter:
        cmd += f' -vf "{scale_filter}"'
    cmd += f' -y {ffmpeg_params} "{target_video_path}"'
    
    # 使用os.system执行ffmpeg命令
    os.system(cmd)
    
    print(f"已转码 {video_path} 到 {target_video_path}")
    
    # 转码完成后去掉 _part 后缀
    final_target_video_path = os.path.join(target_subfolder, video_name + '.mp4')
    os.rename(target_video_path, final_target_video_path)
    print(f"重命名 {target_video_path} 为 {final_target_video_path}")


# 默认源文件夹路径
default_source_folder = os.path.join(os.getcwd(), source_folder)

# 遍历默认源文件夹
for root, dirs, files in os.walk(default_source_folder):
    for file in files:
        file_path = os.path.join(root, file)
        # 检查文件是否为视频文件
        if any(file.endswith(ext) for ext in video_extensions):
            process_video(file_path, target_folder)
        else:
            # 如果文件不是视频文件，将其复制到目标文件夹
            relative_path = os.path.relpath(root, default_source_folder)
            target_subfolder = os.path.join(target_folder, relative_path)
            os.makedirs(target_subfolder, exist_ok=True)
            shutil.copy2(file_path, target_subfolder)
os.system('pause')
