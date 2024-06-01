import os
import shutil
import yaml

# 默认的源文件夹路径和目标文件夹路径
source_folder = 'input'
target_folder = 'output'

# 读取配置文件
with open('config.yaml', encoding='utf-8') as config_file:
    config = yaml.safe_load(config_file)

video_extensions = config['video_extensions']
ffmpeg_params = config['encode_params']
input_params = config['decode_params']

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
    
    # 定义转码后的文件名和路径，加上 .part 后缀
    target_video_name = video_name + '_part' + '.mp4'
    target_video_path = os.path.join(target_subfolder, target_video_name)
    
    # 使用os.system执行ffmpeg命令
    cmd = f'ffmpeg {input_params} -i "{video_path}" -y {ffmpeg_params} "{target_video_path}"'
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
