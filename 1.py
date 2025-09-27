#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站用户视频批量下载器
基于BilibiliDown项目的API分析
支持下载指定用户的所有视频

作者: 根据BilibiliDown项目分析创建
"""

import requests
import json
import os
import time
import hashlib
import urllib.parse
from typing import List, Dict, Optional
import sys


class BilibiliUserDownloader:
    def __init__(self, cookie_string: str = None):
        self.session = requests.Session()
        # 严格按照BilibiliDown项目的配置
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'Connection': 'keep-alive'
        }
        self.session.headers.update(self.headers)
        
        # 设置cookies
        if cookie_string:
            self._set_cookies_from_string(cookie_string)
        else:
            # 设置基础cookies（模拟指纹）
            self._init_fingerprint_cookies()
        
        # WBI签名相关
        self.wbi_img = None
        self.mixin_key = None
        self.mixin_array = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42,
                           19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54,
                           21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]
        
        # 下载配置
        self.download_dir = "./downloads"
        self.max_retries = 3
        self.delay_between_requests = 3  # 增加请求间隔避免限流
        self.api_delay = 2  # API请求前的额外延迟

    def _set_cookies_from_string(self, cookie_string: str):
        """从cookie字符串设置cookies"""
        print("使用用户提供的cookie...")
        
        # 解析cookie字符串
        cookies = {}
        for item in cookie_string.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        
        # 设置到session中
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain='.bilibili.com')
        
        print(f"已设置 {len(cookies)} 个cookie")
    
    def _init_fingerprint_cookies(self):
        """初始化指纹cookies（参考原项目的指纹实现）"""
        import time
        import random
        
        # 模拟原项目的指纹生成
        current_time = int(time.time() * 1000)
        
        # 设置基础cookies
        cookies = {
            'buvid_fp': 'a8bad806241b0b0f7add1024fbd701fa',  # 来自原项目配置
            'b_nut': str(current_time),
            '_uuid': self._generate_uuid(),
            'buvid3': self._generate_buvid3(),
            'b_lsid': self._generate_b_lsid(current_time)
        }
        
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain='.bilibili.com')
    
    def _generate_uuid(self):
        """生成UUID"""
        import uuid
        return str(uuid.uuid4()).replace('-', '')
    
    def _generate_buvid3(self):
        """生成buvid3"""
        import random
        import string
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(32))
    
    def _generate_b_lsid(self, current_time):
        """生成b_lsid"""
        import random
        hex_part = ''.join(random.choice('0123456789ABCDEF') for _ in range(8))
        time_hex = hex(current_time).upper()[2:]
        return f"{hex_part}_{time_hex}"

    def init_wbi_keys(self):
        """初始化WBI签名密钥（参考原项目API.java的实现）"""
        try:
            url = "https://api.bilibili.com/x/web-interface/nav"
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.8',
                'Connection': 'keep-alive'
            }
            
            response = self.session.get(url, headers=headers, timeout=10)
            print(f"WBI初始化响应状态: {response.status_code}")
            
            if response.status_code != 200:
                print(f"WBI初始化失败，状态码: {response.status_code}")
                return False
            
            data = response.json()
            
            if data['code'] == 0:
                wbi_img = data['data']['wbi_img']
                img_url = wbi_img['img_url']
                sub_url = wbi_img['sub_url']
                
                # 提取文件名（严格按照原项目逻辑）
                img_key = img_url.split('/')[-1].split('.')[0]
                sub_key = sub_url.split('/')[-1].split('.')[0]
                
                self.wbi_img = img_key + sub_key
                self.mixin_key = self._get_mixin_key(self.wbi_img)
                print(f"WBI密钥初始化成功: {self.mixin_key}")
                return True
            elif data['code'] == -101:
                # 账号未登录，但仍然可以获取wbi_img
                print("检测到账号未登录状态，但仍可以获取WBI密钥")
                wbi_img = data['data']['wbi_img']
                img_url = wbi_img['img_url']
                sub_url = wbi_img['sub_url']
                
                img_key = img_url.split('/')[-1].split('.')[0]
                sub_key = sub_url.split('/')[-1].split('.')[0]
                
                self.wbi_img = img_key + sub_key
                self.mixin_key = self._get_mixin_key(self.wbi_img)
                print(f"WBI密钥初始化成功: {self.mixin_key}")
                return True
            else:
                print(f"WBI密钥初始化失败: {data}")
                return False
        except Exception as e:
            print(f"WBI密钥初始化错误: {e}")
            return False

    def _get_mixin_key(self, content: str) -> str:
        """生成混合密钥"""
        return ''.join([content[i] for i in self.mixin_array[:32]])

    def _encode_wbi(self, params: dict) -> str:
        """WBI签名"""
        if not self.mixin_key:
            self.init_wbi_keys()
        
        # 添加时间戳
        params['wts'] = int(time.time())
        
        # URL编码并排序
        encoded_params = []
        for k, v in sorted(params.items()):
            encoded_params.append(f"{urllib.parse.quote_plus(str(k))}={urllib.parse.quote_plus(str(v))}")
        
        param_string = '&'.join(encoded_params)
        
        # 计算MD5
        w_rid = hashlib.md5((param_string + self.mixin_key).encode()).hexdigest()
        
        return f"{param_string}&w_rid={w_rid}"

    def extract_user_id(self, user_url: str) -> Optional[str]:
        """从用户空间URL提取用户ID"""
        import re
        
        # 支持多种URL格式
        patterns = [
            r'space\.bilibili\.com/(\d+)',
            r'bilibili\.com/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, user_url)
            if match:
                return match.group(1)
        
        # 如果直接是数字
        if user_url.isdigit():
            return user_url
            
        return None

    def get_user_info_from_medialist(self, user_id: str) -> Optional[Dict]:
        """从 Medialist API 获取用户信息（避免单独请求用户信息API）"""
        try:
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.8',
                'Connection': 'keep-alive',
                'Referer': 'https://space.bilibili.com/',
                'Origin': 'https://space.bilibili.com/'
            }
            
            # 增加延迟
            time.sleep(self.api_delay)
            
            # 获取medialist信息，其中包含用户信息
            info_url = f"https://api.bilibili.com/x/v1/medialist/info?type=1&tid=0&biz_id={user_id}"
            print(f"从Medialist获取用户信息: {info_url}")
            
            response = self.session.get(info_url, headers=headers, timeout=15)
            print(f"Medialist用户信息响应状态: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Medialist用户信息获取失败，状态码: {response.status_code}")
                return None
            
            data = response.json()
            if data['code'] != 0:
                print(f"Medialist用户信息获取失败: {data}")
                return None
            
            # 从 medialist 数据中提取用户信息
            medialist_data = data['data']
            upper_info = medialist_data['upper']
            
            return {
                'mid': upper_info['mid'],
                'name': upper_info['name'],
                'face': upper_info['face'],
                'sign': medialist_data.get('intro', ''),  # 使用列表介绍作为用户简介
                'level': 0,  # medialist中没有等级信息
                'sex': '',
                'official': {'role': 0, 'title': '', 'desc': ''}
            }
            
        except Exception as e:
            print(f"Medialist获取用户信息错误: {e}")
            return None

    def get_user_videos(self, user_id: str, page: int = 1, page_size: int = 50) -> List[Dict]:
        """获取用户投稿视频列表（使用原项目的Medialist方法）"""
        return self._get_user_videos_medialist(user_id, page, page_size)
    
    def _get_user_videos_medialist(self, user_id: str, page: int = 1, page_size: int = 20) -> List[Dict]:
        """使用Medialist API获取用户视频（参考原项目 URL4UPAllMedialistParser）"""
        try:
            # 第一步：获取用户Medialist信息
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.8',
                'Connection': 'keep-alive',
                'Referer': 'https://space.bilibili.com/',
                'Origin': 'https://space.bilibili.com/'
            }
            
            # 增加延迟
            time.sleep(self.api_delay)
            
            # 获取medialist信息
            info_url = f"https://api.bilibili.com/x/v1/medialist/info?type=1&tid=0&biz_id={user_id}"
            print(f"正在获取Medialist信息: {info_url}")
            
            response = self.session.get(info_url, headers=headers, timeout=15)
            print(f"Medialist信息响应状态: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Medialist信息获取失败，状态码: {response.status_code}")
                return []
            
            info_data = response.json()
            if info_data['code'] != 0:
                print(f"Medialist信息获取失败: {info_data}")
                return []
            
            # 第二步：使用medialist resource API获取视频列表
            time.sleep(self.api_delay)
            
            # 构建 resource list URL
            resource_url = f"https://api.bilibili.com/x/v2/medialist/resource/list?type=1&oid=&otype=2&biz_id={user_id}&bvid=&with_current=true&mobi_app=web&ps={page_size}&direction=false&sort_field=1&tid=0&desc=true"
            print(f"正在获取视频列表: {resource_url}")
            
            response = self.session.get(resource_url, headers=headers, timeout=15)
            print(f"Medialist视频列表响应状态: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Medialist视频列表获取失败，状态码: {response.status_code}")
                return []
            
            data = response.json()
            if data['code'] != 0:
                print(f"Medialist视频列表获取失败: {data}")
                return []
            
            # 解析视频列表
            media_list = data['data']['media_list']
            videos = []
            
            for media in media_list:
                # 转换为与原来API兼容的格式
                video = {
                    'bvid': media['bv_id'],
                    'aid': media['id'],
                    'title': media['title'],
                    'pic': media['cover'],
                    'author': media['upper']['name'],
                    'mid': media['upper']['mid'],
                    'created': media['pubtime'],
                    'length': self._format_duration(media.get('duration', 0)),
                    'play': media.get('cnt_info', {}).get('play', 0),
                    'video_review': media.get('cnt_info', {}).get('reply', 0)
                }
                videos.append(video)
            
            print(f"Medialist成功获取 {len(videos)} 个视频")
            return videos
            
        except Exception as e:
            print(f"Medialist获取视频列表错误: {e}")
            return []
    
    def _format_duration(self, seconds):
        """格式化时长"""
        if seconds == 0:
            return "0:00"
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    def _get_user_videos_wbi(self, user_id: str, page: int = 1, page_size: int = 50) -> List[Dict]:
        """使用WBI签名获取用户投稿视频列表"""
        # 构建参数
        params = {
            'mid': user_id,
            'ps': page_size,
            'tid': 0,
            'pn': page,
            'keyword': '',
            'order': 'pubdate',  # 按发布时间排序
            'platform': 'web',
            'web_location': '1550101'
        }
        
        # WBI签名
        query_string = self._encode_wbi(params)
        url = f"https://api.bilibili.com/x/space/wbi/arc/search?{query_string}"
        
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': f'https://space.bilibili.com/{user_id}/video',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.8'
        }
        
        try:
            response = self.session.get(url, headers=headers, timeout=15)
            print(f"WBI视频列表响应状态: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            if data['code'] == 0:
                video_list = data['data']['list']['vlist']
                return video_list
            elif data['code'] == -352:
                print(f"WBI API被风控，自动降级到普通API")
                return []  # 返回空列表，触发降级
            else:
                print(f"WBI获取视频列表失败 (页 {page}): {data}")
                return []
        except Exception as e:
            print(f"WBI获取视频列表错误 (页 {page}): {e}")
            return []
    
    def _get_user_videos_fallback(self, user_id: str, page: int = 1, page_size: int = 50) -> List[Dict]:
        """降级方案：使用普通API获取用户投稿视频列表"""
        # 使用更简单的API，减少风控风险
        url = f"https://api.bilibili.com/x/space/arc/search?mid={user_id}&ps={page_size}&tid=0&pn={page}&keyword=&order=pubdate&jsonp=jsonp"
        
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': f'https://space.bilibili.com/{user_id}/video',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'Connection': 'keep-alive'
        }
        
        # 重试机制处理频率限制
        for attempt in range(self.max_retries):
            try:
                # 增加延迟，降低风控风险
                if attempt > 0:
                    wait_time = self.api_delay * (2 **attempt)  # 指数退避
                    print(f"第{attempt + 1}次尝试，等待{wait_time}秒...")
                    time.sleep(wait_time)
                else:
                    time.sleep(self.api_delay)
                
                response = self.session.get(url, headers=headers, timeout=15)
                print(f"普通API视频列表响应状态: {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                
                if data['code'] == 0:
                    video_list = data['data']['list']['vlist']
                    return video_list
                elif data['code'] == -799:
                    print(f"请求过于频繁（第{attempt + 1}次尝试），稍后重试...")
                    if attempt == self.max_retries - 1:
                        print("所有重试均失败，建议稍后再试或增加延迟时间")
                    continue
                elif data['code'] == -352:
                    print(f"普通API也被风控，建议增加延迟或稍后再试")
                    return []
                else:
                    print(f"普通API获取视频列表失败 (页 {page}): {data}")
                    return []
            except Exception as e:
                print(f"普通API获取视频列表错误 (页 {page}, 第{attempt + 1}次尝试): {e}")
                if attempt == self.max_retries - 1:
                    return []
        
        return []

    def get_all_user_videos(self, user_id: str, max_count: int = None) -> List[Dict]:
        """获取用户投稿视频（使用Medialist方法），支持限制数量"""
        all_videos = []
        page = 1
        page_size = 20  # 原项目使用的页大小
        
        print(f"开始获取用户 {user_id} 的视频（使用Medialist方法）...")
        if max_count:
            print(f"目标获取数量: {max_count} 个视频")
        
        while True:
            print(f"正在获取第 {page} 页...")
            videos = self.get_user_videos(user_id, page, page_size)
            
            if not videos:
                break
            
            # 检查是否需要限制数量
            if max_count and len(all_videos) + len(videos) > max_count:
                # 只取需要的数量
                needed = max_count - len(all_videos)
                videos = videos[:needed]
                all_videos.extend(videos)
                print(f"第 {page} 页获取到 {len(videos)} 个视频（已达到目标数量 {max_count}）")
                break
            
            all_videos.extend(videos)
            print(f"第 {page} 页获取到 {len(videos)} 个视频，累计 {len(all_videos)} 个")
            
            # 如果已达到目标数量，停止获取
            if max_count and len(all_videos) >= max_count:
                print(f"已获取到目标数量 {max_count} 个视频")
                break
            
            # 如果获取的视频数少于页大小，说明是最后一页
            if len(videos) < page_size:
                break
                
            page += 1
            # 严格控制请求频率
            time.sleep(self.delay_between_requests)
        
        print(f"共获取到 {len(all_videos)} 个视频")
        return all_videos


    def get_video_cid(self, bvid: str) -> Optional[str]:
        """获取视频的cid"""
        try:
            url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Referer': f'https://www.bilibili.com/video/{bvid}',
                'Accept': 'application/json, text/plain, */*'
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data['code'] == 0:
                    # 获取第一个分P的cid
                    pages = data['data']['pages']
                    if pages:
                        return str(pages[0]['cid'])
            return None
        except Exception as e:
            print(f"获取视频cid失败 {bvid}: {e}")
            return None

    def download_video_file(self, url: str, filename: str) -> bool:
        """下载视频文件"""
        try:
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Referer': 'https://www.bilibili.com/',
                'Range': 'bytes=0-'  # 支持断点续传
            }
            
            print(f"正在下载: {filename}")
            response = self.session.get(url, headers=headers, stream=True, timeout=30)
            
            if response.status_code in [200, 206]:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # 显示下载进度
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                print(f"\r下载进度: {progress:.1f}% ({downloaded}/{total_size})", end='')
                
                print(f"\n✓ 下载完成: {filename}")
                return True
            else:
                print(f"下载失败，状态码: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"下载文件时出错: {e}")
            return False

    def merge_video_audio(self, video_file: str, audio_file: str, output_file: str) -> bool:
        """合并视频和音频文件"""
        try:
            import subprocess
            
            # 检查ffmpeg是否可用
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("警告: 未找到ffmpeg，将尝试简单合并或仅保存视频文件")
                # 如果没有ffmpeg，至少保存视频文件
                if os.path.exists(video_file):
                    os.rename(video_file, output_file)
                    return True
                return False
            
            # 使用ffmpeg合并音视频
            cmd = [
                'ffmpeg', '-i', video_file, '-i', audio_file,
                '-c', 'copy', '-y', output_file
            ]
            
            print("正在合并音视频...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 删除临时文件
                if os.path.exists(video_file):
                    os.remove(video_file)
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                print("✓ 音视频合并完成")
                return True
            else:
                print(f"ffmpeg合并失败: {result.stderr}")
                # 保留视频文件
                if os.path.exists(video_file):
                    os.rename(video_file, output_file)
                    print("已保存视频文件（无音频）")
                return True
                
        except Exception as e:
            print(f"合并音视频时出错: {e}")
            # 保留视频文件
            if os.path.exists(video_file):
                os.rename(video_file, output_file)
                print("已保存视频文件（无音频）")
            return True

    def _download_video(self, video: Dict) -> bool:
        """下载单个视频（支持音视频分离格式）"""
        try:
            print(f"\n开始下载: {video['title']}")
            
            # 创建下载目录
            os.makedirs(self.download_dir, exist_ok=True)
            
            # 1. 获取视频的cid
            cid = self.get_video_cid(video['bvid'])
            if not cid:
                print(f"获取cid失败: {video['bvid']}")
                return False
            
            print(f"获取到cid: {cid}")
            
            # 2. 获取下载链接
            download_data = self.get_video_download_url(video['bvid'], cid)
            if not download_data:
                print(f"获取下载链接失败: {video['bvid']}")
                return False
            
            # 清理文件名中的非法字符
            safe_title = "".join(c for c in video['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
            base_filename = f"{video['bvid']}_{safe_title}"
            final_filepath = os.path.join(self.download_dir, f"{base_filename}.mp4")
            
            # 3. 解析下载链接
            if 'dash' in download_data and download_data['dash']:
                # DASH格式 - 音视频分离
                dash_data = download_data['dash']
                
                video_url = None
                audio_url = None
                
                # 获取视频流
                if 'video' in dash_data and dash_data['video']:
                    video_streams = dash_data['video']
                    # 选择最高质量的视频流
                    video_url = video_streams[0]['baseUrl']
                
                # 获取音频流
                if 'audio' in dash_data and dash_data['audio']:
                    audio_streams = dash_data['audio']
                    # 选择最高质量的音频流
                    audio_url = audio_streams[0]['baseUrl']
                
                if not video_url:
                    print(f"未找到视频流: {video['bvid']}")
                    return False
                
                # 下载视频文件
                video_temp_file = os.path.join(self.download_dir, f"{base_filename}_video.tmp")
                print("下载视频流...")
                if not self.download_video_file(video_url, video_temp_file):
                    return False
                
                # 下载音频文件（如果存在）
                audio_temp_file = None
                if audio_url:
                    audio_temp_file = os.path.join(self.download_dir, f"{base_filename}_audio.tmp")
                    print("下载音频流...")
                    if not self.download_video_file(audio_url, audio_temp_file):
                        print("音频下载失败，将保存无音频视频")
                        audio_temp_file = None
                
                # 合并音视频
                if audio_temp_file and os.path.exists(audio_temp_file):
                    success = self.merge_video_audio(video_temp_file, audio_temp_file, final_filepath)
                else:
                    # 只有视频，直接重命名
                    print("只保存视频文件（无音频）")
                    os.rename(video_temp_file, final_filepath)
                    success = True
                    
            elif 'durl' in download_data and download_data['durl']:
                # FLV格式 - 音视频一体
                video_url = download_data['durl'][0]['url']
                print("下载FLV格式视频（包含音频）...")
                success = self.download_video_file(video_url, final_filepath)
            else:
                print(f"未找到可用的下载链接: {video['bvid']}")
                return False
            
            if success:
                # 创建信息文件
                info_file = os.path.join(self.download_dir, f"{video['bvid']}_info.txt")
                with open(info_file, 'w', encoding='utf-8') as f:
                    f.write(f"标题: {video['title']}\n")
                    f.write(f"BV号: {video['bvid']}\n")
                    f.write(f"作者: {video['author']}\n")
                    f.write(f"时长: {video['length']}\n")
                    f.write(f"播放量: {video['play']}\n")
                    f.write(f"文件名: {base_filename}.mp4\n")
                
                return True
            else:
                return False
            
        except Exception as e:
            print(f"下载视频 {video['title']} 时出错: {e}")
            return False

    def get_video_download_url(self, bvid: str, cid: str, quality: int = 80) -> Optional[Dict]:
        """获取视频下载链接"""
        # 构建参数
        params = {
            'bvid': bvid,
            'cid': cid,
            'qn': quality,
            'fnver': 0,
            'fnval': 4048,  # DASH格式
            'fourk': 1
        }
        
        # WBI签名
        query_string = self._encode_wbi(params)
        url = f"https://api.bilibili.com/x/player/wbi/playurl?{query_string}"
        
        try:
            response = self.session.get(url)
            data = response.json()
            
            if data['code'] == 0:
                return data['data']
            else:
                print(f"获取视频下载链接失败 {bvid}: {data}")
                return None
        except Exception as e:
            print(f"获取视频下载链接错误 {bvid}: {e}")
            return None


def check_ffmpeg():
    """检查ffmpeg是否可用"""
    try:
        import subprocess
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def main():
    """B站用户视频批量下载器主函数"""
    print("===== B站用户视频批量下载器 =====")
    
    # 检查ffmpeg
    if not check_ffmpeg():
        print("⚠️  警告: 未检测到ffmpeg")
        print("   为了下载有声音的视频，建议安装ffmpeg:")
        print("   - Windows: 下载 https://ffmpeg.org/download.html 并添加到PATH")
        print("   - macOS: brew install ffmpeg")
        print("   - Linux: sudo apt install ffmpeg 或 sudo yum install ffmpeg")
        print("   没有ffmpeg将只能下载无声音的视频文件")
        
        continue_choice = input("\n是否继续下载？(y/n): ").strip().lower()
        if continue_choice != 'y':
            print("程序退出")
            return
        print()
    else:
        print("✓ 检测到ffmpeg，支持音视频合并")
        print()
    
    # 交互式输入用户信息
    user_url = input("请输入B站用户空间链接或用户ID: ").strip()
    cookie_str = input("请输入Cookie（可选，直接回车跳过）: ").strip()
    max_videos_input = input("请输入最大下载数量（可选，直接回车下载全部）: ").strip()
    output_dir = input("请输入下载目录（可选，直接回车使用默认目录./downloads）: ").strip()
    delay_input = input("请输入请求间隔时间（秒，默认3秒）: ").strip()

    # 处理输入参数
    max_videos = int(max_videos_input) if max_videos_input else None
    download_dir = output_dir if output_dir else "./downloads"
    delay = int(delay_input) if delay_input and delay_input.isdigit() else 3

    # 初始化下载器
    downloader = BilibiliUserDownloader(cookie_str)
    downloader.download_dir = download_dir
    downloader.delay_between_requests = delay

    # 初始化WBI密钥
    if not downloader.init_wbi_keys():
        print("WBI密钥初始化失败，程序退出")
        return

    # 提取用户ID
    user_id = downloader.extract_user_id(user_url)
    if not user_id:
        print("无法从输入中提取用户ID，请检查链接是否正确")
        return
    print(f"提取到用户ID: {user_id}")

    # 获取用户信息
    user_info = downloader.get_user_info_from_medialist(user_id)
    if user_info:
        print(f"用户信息: {user_info['name']}（ID: {user_info['mid']}）")
    else:
        print("无法获取用户信息，继续尝试下载视频")

    # 获取视频列表（按需获取指定数量）
    print("\n开始获取视频列表...")
    all_videos = downloader.get_all_user_videos(user_id, max_videos)
    if not all_videos:
        print("未获取到任何视频，程序退出")
        return

    print(f"\n准备下载 {len(all_videos)} 个视频...")
    print("=" * 50)

    # 开始下载
    success_count = 0
    fail_count = 0
    
    for idx, video in enumerate(all_videos, 1):
        print(f"\n===== 处理第 {idx}/{len(all_videos)} 个视频 =====")
        print(f"标题: {video['title']}")
        print(f"BV号: {video['bvid']}")
        print(f"作者: {video['author']}")
        print(f"时长: {video['length']}")
        
        success = downloader._download_video(video)
        if success:
            success_count += 1
            print(f"✓ 第 {idx} 个视频下载完成")
        else:
            fail_count += 1
            print(f"✗ 第 {idx} 个视频下载失败")
        
        # 下载间隔
        if idx < len(all_videos):
            print(f"等待 {delay} 秒后继续下载...")
            time.sleep(delay)
    
    # 下载完成统计
    print("\n" + "=" * 50)
    print("下载完成！")
    print(f"成功下载: {success_count} 个视频")
    print(f"下载失败: {fail_count} 个视频")
    print(f"下载目录: {download_dir}")
    print("=" * 50)


if __name__ == "__main__":
    main()