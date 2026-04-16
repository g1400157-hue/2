#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BK Server Manager - Modern Web Interface
Современный веб-интерфейс для управления серверами BK
"""

from flask import Flask, render_template_string, request, jsonify, send_file
import socket
import ssl
import json
import logging
import os
import threading
import time
from datetime import datetime
import warnings
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
import openpyxl

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- КОНФИГУРАЦИЯ ---
CONFIG = {
    'password': '12346',
    'ntp_expected': 'msk-v-dc01.bk.local,msk-v-dc02.bk.local',
    'web_enable_value': 1,
    'timeout': 5,
    'log_file': 'bk_manager_web.log',
    'templates_file': 'user_templates.json'
}

if getattr(__import__('sys'), 'frozen', False):
    base_path = os.path.dirname(__import__('sys').executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

log_path = os.path.join(base_path, CONFIG['log_file'])
templates_path = os.path.join(base_path, CONFIG['templates_file'])

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(log_path, encoding='utf-8', mode='a')]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Цвета для Excel
FILL_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
FILL_RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
FILL_YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
FONT_BOLD = Font(bold=True)
CENTER_ALIGN = Alignment(horizontal="center", vertical="center")

# Хранилище результатов
RESULTS_STORE = {
    'ntp': [], 'web': [], 'cloud': [], 'version': [],
    'archive': [], 'users_list': [], 'users_check': [],
    'db': [], 'pos': [], 'ip': []
}

# --- БАЗА ЭТАЛОНОВ ПРАВОК ---
class UserTemplatesDB:
    """Управление базой эталонов прав пользователей по версиям"""
    DEFAULT_TEMPLATES = {
        '4.3': {
            'Admin': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 1,
                    'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 1,
                    'view_button': 1, 'can_change_password': 1, 'base_rights': 75631},
            'KRU': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                    'templates_managing': 1, 'templates_sharing': 1, 'settings_button': 1, 'shutdown_button': 0, 
                    'view_button': 1, 'can_change_password': 0, 'base_rights': 1315},
            'OPS': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                    'templates_managing': 1, 'templates_sharing': 1, 'settings_button': 1, 'shutdown_button': 0, 
                    'view_button': 1, 'can_change_password': 0, 'base_rights': 291},
            'Manager': {'enable_web': 0, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                    'templates_managing': 1, 'templates_sharing': 1, 'settings_button': 1, 'shutdown_button': 0, 
                    'view_button': 0, 'can_change_password': 0, 'base_rights': 291}
        },
        '4.5': {
            'Admin': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 1,
                    'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 1,
                    'view_button': 1, 'can_change_password': 1, 'base_rights': 75631},
            'KRU': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                    'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 0,
                    'view_button': 1, 'can_change_password': 0, 'base_rights': 75043},
            'OPS': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                    'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 0,
                    'view_button': 1, 'can_change_password': 0, 'base_rights': 74019},
            'Manager': {'enable_web': 0, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                        'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 0,
                        'view_button': 0, 'can_change_password': 0, 'base_rights': 8483}
        },
        '4.6+': {
            'Admin': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 1,
                    'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 1,
                    'view_button': 1, 'can_change_password': 1, 'base_rights': 75631},
            'KRU': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                    'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 0,
                    'view_button': 1, 'can_change_password': 0, 'base_rights': 1575},
            'OPS': {'enable_web': 1, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                    'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 0,
                    'view_button': 1, 'can_change_password': 0, 'base_rights': 8995},
            'Manager': {'enable_web': 0, 'enable_local': 1, 'enable_remote': 1, 'enable_analytics': 0,
                        'templates_managing': 1, 'templates_sharing': 1, 'shutdown_button': 0,
                        'view_button': 0, 'can_change_password': 0, 'base_rights': 803}
        }
    }
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.templates = self.load()
    
    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    templates = self.DEFAULT_TEMPLATES.copy()
                    templates.update(loaded)
                    return templates
            except:
                pass
        return self.DEFAULT_TEMPLATES.copy()
    
    def save(self):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.templates, f, indent=2, ensure_ascii=False)
    
    def get_template(self, version, user_type):
        if not version or version in ['Неизвестно', '', '-']:
            ver_key = '4.5'
        elif version.startswith('4.3') or version.startswith('4.4'):
            ver_key = '4.3'
        elif version.startswith('4.5'):
            ver_key = '4.5'
        else:
            ver_key = '4.6+'
        if ver_key in self.templates and user_type in self.templates[ver_key]:
            return self.templates[ver_key][user_type], ver_key
        return None, ver_key
    
    def save_template(self, version, user_type, settings):
        if version.startswith('4.3') or version.startswith('4.4'):
            ver_key = '4.3'
        elif version.startswith('4.5'):
            ver_key = '4.5'
        else:
            ver_key = '4.6+'
        if ver_key not in self.templates:
            self.templates[ver_key] = {}
        self.templates[ver_key][user_type] = settings
        self.save()
    
    def get_all_versions(self):
        return list(self.templates.keys())
    
    def get_all_users_for_version(self, version):
        if version in self.templates:
            return list(self.templates[version].keys())
        return []

templates_db = UserTemplatesDB(templates_path)

# --- СЕТЕВАЯ ЧАСТЬ ---
def create_no_alpn_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try: context.set_alpn_protocols([])
    except AttributeError: pass
    context.set_ciphers('DEFAULT:@SECLEVEL=1')
    try: context.minimum_version = ssl.TLSVersion.TLSv1
    except (AttributeError, ValueError): context.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3
    return context

def make_request(host, port, path, method='GET', data=None, sid=None):
    url_path = path
    if sid is not None:
        separator = '&' if '?' in url_path else '?'
        url_path += f"{separator}sid={sid}"
    body_content = ""
    data_exists = False
    if data is not None and len(str(data)) > 0:
        data_exists = True
    request_lines = [
        f"{method} /{url_path} HTTP/1.1",
        f"Host: {host}:{port}",
        "User-Agent: BK-Manager-Web/1.0",
        "Accept: */*",
        "Connection: close"
    ]
    if data_exists:
        request_lines.append("Content-Type: application/x-www-form-urlencoded")
        request_lines.append(f"Content-Length: {len(str(data))}")
        body_content = str(data)
    request_str = "\r\n".join(request_lines) + "\r\n\r\n" + body_content
    context = create_no_alpn_context()
    try:
        sock = socket.create_connection((host, port), timeout=CONFIG['timeout'])
        ssock = context.wrap_socket(sock, server_hostname=host)
        ssock.sendall(request_str.encode('utf-8'))
        response_data = b""
        while True:
            chunk = ssock.recv(4096)
            if not chunk: break
            response_data += chunk
        ssock.close()
        resp_text = response_data.decode('utf-8', errors='ignore')
        if '\r\n\r\n' in resp_text:
            _, body = resp_text.split('\r\n\r\n', 1)
            body = body.strip()
            if body.startswith('{'):
                end_idx = body.rfind('}') + 1
                if end_idx > 0: return json.loads(body[:end_idx])
            return json.loads(body)
        return None
    except Exception:
        return None

def is_success(response):
    if response is None: return False
    val = response.get('success')
    if val is None: return False
    return str(val) == "1"

def parse_server_url(url_string):
    url_string = url_string.strip()
    if not url_string or url_string.startswith('#'): return None
    if '://' in url_string: url_string = url_string.split('://', 1)[1]
    if ':' in url_string:
        parts = url_string.split(':')
        host = parts[0]
        try: port = int(parts[1].split('/')[0])
        except ValueError: port = 8080
    else:
        host = url_string
        port = 8080
    return {'host': host, 'port': port, 'original': url_string}

# --- ЛОГИКА ЗАДАЧ ---
def check_ntp_single(host, port):
    path_get = f"settings/time_setup/ntp_servers?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None: return False, "Нет соединения", "", ""
    current_val = data.get('value', '')
    curr_sorted = ','.join(sorted([x.strip() for x in str(current_val).split(',')]))
    exp_sorted = ','.join(sorted([x.strip() for x in CONFIG['ntp_expected'].split(',')]))
    if curr_sorted == exp_sorted:
        return True, "Конфигурация корректна", current_val, CONFIG['ntp_expected']
    login_resp = make_request(host, port, f"login?password={CONFIG['password']}", method='POST')
    if not is_success(login_resp) or not login_resp.get('sid'):
        return False, "Ошибка входа", current_val, CONFIG['ntp_expected']
    sid = login_resp['sid']
    update_path = f"settings/time_setup/ntp_servers={CONFIG['ntp_expected']}"
    body = f"ntp_servers={CONFIG['ntp_expected']}"
    update_resp = make_request(host, port, update_path, method='POST', data=body, sid=sid)
    if is_success(update_resp):
        check_data = make_request(host, port, path_get)
        if check_data is not None:
            new_val = check_data.get('value', '')
            new_sorted = ','.join(sorted([x.strip() for x in str(new_val).split(',')]))
            if new_sorted == exp_sorted:
                return True, "Исправлено", new_val, CONFIG['ntp_expected']
    return False, "Ошибка записи", current_val, CONFIG['ntp_expected']

def check_web_status(host, port):
    path_get = f"settings/webserver/enable_webview?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None:
        return False, "Нет соединения", None
    current_val = data.get('value')
    if current_val is None:
        path_get = f"settings/webserver/enable_sdk?password={CONFIG['password']}"
        data = make_request(host, port, path_get)
        if data is None:
            return False, "Нет соединения", None
        current_val = data.get('value')
    status = "Включен" if current_val == 1 else "Выключен"
    return True, status, current_val

def set_web_status(host, port, value):
    login_resp = make_request(host, port, f"login?password={CONFIG['password']}", method='POST')
    if not is_success(login_resp) or not login_resp.get('sid'):
        return False, "Ошибка входа"
    sid = login_resp['sid']
    update_path = f"settings/webserver/enable_webview={value}"
    body = f"enable_webview={value}"
    for attempt in range(3):
        update_resp = make_request(host, port, update_path, method='POST', data=body, sid=sid)
        if is_success(update_resp):
            time.sleep(0.5)
            for check_attempt in range(3):
                time.sleep(0.3)
                check_data = make_request(host, port, f"settings/webserver/enable_webview?sid={sid}")
                if check_data is not None and check_data.get('value') == value:
                    return True, "Web включен" if value == 1 else "Web выключен"
            return True, "Web включен" if value == 1 else "Web выключен"
    return False, "Ошибка записи"

def check_cloud_status(host, port):
    path_get = f"settings/cloud/cloud_enabled?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None:
        return False, "Нет соединения", None
    current_val = data.get('value')
    if current_val is None:
        return False, "Параметр не найден", None
    status = "Включено" if current_val == 1 else "Выключено"
    return True, status, current_val

def set_cloud_status(host, port, target_value):
    path_get = f"settings/cloud/cloud_enabled?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None:
        return False, "Нет соединения"
    current_val = data.get('value')
    if current_val == target_value:
        status_msg = "Включено" if target_value == 1 else "Выключено"
        return True, f"Уже {status_msg}"
    login_resp = make_request(host, port, f"login?password={CONFIG['password']}", method='POST')
    if not is_success(login_resp) or not login_resp.get('sid'):
        return False, "Ошибка входа"
    sid = login_resp['sid']
    update_path = f"settings/cloud/cloud_enabled={target_value}"
    body = f"cloud_enabled={target_value}"
    update_resp = make_request(host, port, update_path, method='POST', data=body, sid=sid)
    if is_success(update_resp):
        time.sleep(0.5)
        check_data = make_request(host, port, path_get)
        if check_data is not None and check_data.get('value') == target_value:
            status_msg = "Включено" if target_value == 1 else "Выключено"
            return True, f"Изменено: {status_msg}"
    return False, "Ошибка записи"

def check_version_single(host, port):
    path_get = f"settings/health/product_version?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None: return False, "Нет соединения", ""
    version = data.get('value', data.get('product_version', 'Неизвестно'))
    return True, "Версия получена", str(version)

def check_archive_days(host, port, stream_type):
    path_get = f"streams/{stream_type}/archive_depth?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None: return False, "Нет соединения", ""
    days = data.get('value', data.get('archive_depth', '0'))
    return True, "OK", str(days)

def check_database_status(host, port):
    path_get = f"health?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None: return False, "Нет соединения", "", ""
    db_status = data.get('database', 'unknown')
    db_size = data.get('database_size', 'N/A')
    status_map = {'ok': ('OK', 'green'), 'degraded': ('Деградирована', 'yellow'), 'critical': ('Критическая', 'red')}
    status_info = status_map.get(str(db_status).lower(), ('Неизвестно', 'gray'))
    return True, status_info[0], str(db_size), status_info[1]

def check_pos_terminal(host, port, folder_name):
    path_get = f"pos_folder2/{folder_name}/terminals?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None: return False, "Нет соединения", []
    terminals = data.get('terminals', [])
    if not isinstance(terminals, list): terminals = []
    return True, "OK", terminals

def get_server_ip(host, port, interface='enp1s0'):
    path_get = f"network_interfaces/{interface}/ip?password={CONFIG['password']}"
    data = make_request(host, port, path_get)
    if data is None: return False, "Нет соединения", ""
    ip = data.get('value', data.get('ip', ''))
    if isinstance(ip, list) and len(ip) > 0: ip = ip[0]
    return True, "OK", str(ip)

def process_servers(servers_list, task_type, extra_params=None):
    results = []
    for server_str in servers_list:
        parsed = parse_server_url(server_str)
        if not parsed: continue
        host, port = parsed['host'], parsed['port']
        
        if task_type == 'ntp':
            success, status, current, expected = check_ntp_single(host, port)
            results.append({'server': parsed['original'], 'success': success, 'status': status, 
                          'current': current, 'expected': expected})
        
        elif task_type == 'web':
            action = extra_params.get('action', 'check') if extra_params else 'check'
            if action == 'enable':
                success, status = set_web_status(host, port, 1)
            elif action == 'disable':
                success, status = set_web_status(host, port, 0)
            else:
                success, status, current = check_web_status(host, port)
            results.append({'server': parsed['original'], 'success': success, 'status': status})
        
        elif task_type == 'cloud':
            action = extra_params.get('action', 'check') if extra_params else 'check'
            if action == 'enable':
                success, status = set_cloud_status(host, port, 1)
            elif action == 'disable':
                success, status = set_cloud_status(host, port, 0)
            else:
                success, status, current = check_cloud_status(host, port)
            results.append({'server': parsed['original'], 'success': success, 'status': status})
        
        elif task_type == 'version':
            success, status, version = check_version_single(host, port)
            results.append({'server': parsed['original'], 'success': success, 'status': status, 'version': version})
        
        elif task_type == 'archive':
            stream_type = extra_params.get('stream_type', 'main') if extra_params else 'main'
            success, status, days = check_archive_days(host, port, stream_type)
            results.append({'server': parsed['original'], 'success': success, 'status': status, 'days': days})
        
        elif task_type == 'db':
            success, status, size, color = check_database_status(host, port)
            results.append({'server': parsed['original'], 'success': success, 'status': status, 
                          'size': size, 'color': color})
        
        elif task_type == 'pos':
            folder_name = extra_params.get('folder', 'pos_folder2') if extra_params else 'pos_folder2'
            success, status, terminals = check_pos_terminal(host, port, folder_name)
            results.append({'server': parsed['original'], 'success': success, 'status': status, 
                          'terminals': terminals, 'count': len(terminals)})
        
        elif task_type == 'ip':
            interface = extra_params.get('interface', 'enp1s0') if extra_params else 'enp1s0'
            success, status, ip = get_server_ip(host, port, interface)
            results.append({'server': parsed['original'], 'success': success, 'status': status, 'ip': ip})
        
        time.sleep(0.1)
    
    return results

# HTML шаблон современного интерфейса
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BK Server Manager - Современный Интерфейс</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; font-size: 1.1em; }
        .content { padding: 30px; }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        .tab-btn {
            padding: 12px 24px;
            border: none;
            background: #ecf0f1;
            color: #2c3e50;
            border-radius: 10px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .tab-btn:hover { background: #bdc3c7; transform: translateY(-2px); }
        .tab-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.5s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .input-group { margin-bottom: 20px; }
        .input-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #2c3e50;
        }
        textarea, input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ecf0f1;
            border-radius: 10px;
            font-size: 1em;
            transition: border-color 0.3s ease;
        }
        textarea:focus, input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        textarea { min-height: 120px; resize: vertical; }
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 10px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-right: 10px;
            margin-bottom: 10px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4); }
        .btn-success { background: #27ae60; color: white; }
        .btn-success:hover { background: #2ecc71; transform: translateY(-2px); }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-danger:hover { background: #c0392b; transform: translateY(-2px); }
        .btn-secondary { background: #95a5a6; color: white; }
        .btn-secondary:hover { background: #7f8c8d; transform: translateY(-2px); }
        .results-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .results-table th, .results-table td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }
        .results-table th {
            background: #2c3e50;
            color: white;
            font-weight: 600;
        }
        .results-table tr:hover { background: #f8f9fa; }
        .status-badge {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
            display: inline-block;
        }
        .status-success { background: #d4edda; color: #155724; }
        .status-error { background: #f8d7da; color: #721c24; }
        .status-warning { background: #fff3cd; color: #856404; }
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }
        .loading.active { display: block; }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .card h3 { margin-bottom: 15px; color: #2c3e50; }
        .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .progress-bar {
            width: 100%;
            height: 10px;
            background: #ecf0f1;
            border-radius: 5px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖥️ BK Server Manager</h1>
            <p>Современная панель управления серверами TRASSIR</p>
        </div>
        
        <div class="content">
            <div class="tabs">
                <button class="tab-btn active" data-tab="ntp">⏰ NTP Серверы</button>
                <button class="tab-btn" data-tab="web">🌐 Web Интерфейс</button>
                <button class="tab-btn" data-tab="cloud">☁️ Cloud</button>
                <button class="tab-btn" data-tab="version">📋 Версии</button>
                <button class="tab-btn" data-tab="archive">📦 Архив</button>
                <button class="tab-btn" data-tab="db">💾 База Данных</button>
                <button class="tab-btn" data-tab="pos">🧾 POS Терминалы</button>
                <button class="tab-btn" data-tab="ip">🌍 IP Адреса</button>
            </div>

            <!-- NTP Tab -->
            <div class="tab-content active" id="ntp-tab">
                <div class="card">
                    <h3>Проверка и настройка NTP серверов</h3>
                    <div class="input-group">
                        <label>Список серверов (формат: host:port или host)</label>
                        <textarea id="ntp-servers" placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"></textarea>
                    </div>
                    <button class="btn btn-primary" onclick="runTask('ntp')">Запустить проверку</button>
                </div>
                <div id="ntp-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Выполнение задачи...</p>
                </div>
                <div id="ntp-results"></div>
            </div>

            <!-- Web Tab -->
            <div class="tab-content" id="web-tab">
                <div class="card">
                    <h3>Управление Web интерфейсом</h3>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Список серверов</label>
                            <textarea id="web-servers" placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"></textarea>
                        </div>
                        <div class="input-group">
                            <label>Действие</label>
                            <select id="web-action">
                                <option value="check">Проверить статус</option>
                                <option value="enable">Включить</option>
                                <option value="disable">Выключить</option>
                            </select>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="runTask('web')">Выполнить</button>
                </div>
                <div id="web-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Выполнение задачи...</p>
                </div>
                <div id="web-results"></div>
            </div>

            <!-- Cloud Tab -->
            <div class="tab-content" id="cloud-tab">
                <div class="card">
                    <h3>Управление Cloud подключением</h3>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Список серверов</label>
                            <textarea id="cloud-servers" placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"></textarea>
                        </div>
                        <div class="input-group">
                            <label>Действие</label>
                            <select id="cloud-action">
                                <option value="check">Проверить статус</option>
                                <option value="enable">Включить</option>
                                <option value="disable">Выключить</option>
                            </select>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="runTask('cloud')">Выполнить</button>
                </div>
                <div id="cloud-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Выполнение задачи...</p>
                </div>
                <div id="cloud-results"></div>
            </div>

            <!-- Version Tab -->
            <div class="tab-content" id="version-tab">
                <div class="card">
                    <h3>Проверка версий TRASSIR</h3>
                    <div class="input-group">
                        <label>Список серверов</label>
                        <textarea id="version-servers" placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"></textarea>
                    </div>
                    <button class="btn btn-primary" onclick="runTask('version')">Получить версии</button>
                </div>
                <div id="version-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Выполнение задачи...</p>
                </div>
                <div id="version-results"></div>
            </div>

            <!-- Archive Tab -->
            <div class="tab-content" id="archive-tab">
                <div class="card">
                    <h3>Проверка глубины архива</h3>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Список серверов</label>
                            <textarea id="archive-servers" placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"></textarea>
                        </div>
                        <div class="input-group">
                            <label>Тип потока</label>
                            <select id="archive-stream">
                                <option value="main">Основной</option>
                                <option value="high">Высокий</option>
                                <option value="low">Низкий</option>
                            </select>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="runTask('archive')">Проверить</button>
                </div>
                <div id="archive-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Выполнение задачи...</p>
                </div>
                <div id="archive-results"></div>
            </div>

            <!-- Database Tab -->
            <div class="tab-content" id="db-tab">
                <div class="card">
                    <h3>Статус базы данных</h3>
                    <div class="input-group">
                        <label>Список серверов</label>
                        <textarea id="db-servers" placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"></textarea>
                    </div>
                    <button class="btn btn-primary" onclick="runTask('db')">Проверить БД</button>
                </div>
                <div id="db-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Выполнение задачи...</p>
                </div>
                <div id="db-results"></div>
            </div>

            <!-- POS Tab -->
            <div class="tab-content" id="pos-tab">
                <div class="card">
                    <h3>POS Терминалы</h3>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Список серверов</label>
                            <textarea id="pos-servers" placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"></textarea>
                        </div>
                        <div class="input-group">
                            <label>Папка POS</label>
                            <input type="text" id="pos-folder" value="pos_folder2" placeholder="pos_folder2">
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="runTask('pos')">Получить список</button>
                </div>
                <div id="pos-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Выполнение задачи...</p>
                </div>
                <div id="pos-results"></div>
            </div>

            <!-- IP Tab -->
            <div class="tab-content" id="ip-tab">
                <div class="card">
                    <h3>IP Адреса серверов</h3>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Список серверов</label>
                            <textarea id="ip-servers" placeholder="192.168.1.1:8080&#10;192.168.1.2:8080"></textarea>
                        </div>
                        <div class="input-group">
                            <label>Интерфейс</label>
                            <input type="text" id="ip-interface" value="enp1s0" placeholder="enp1s0">
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="runTask('ip')">Получить IP</button>
                </div>
                <div id="ip-loading" class="loading">
                    <div class="spinner"></div>
                    <p>Выполнение задачи...</p>
                </div>
                <div id="ip-results"></div>
            </div>
        </div>
    </div>

    <script>
        // Tabs functionality
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(btn.dataset.tab + '-tab').classList.add('active');
            });
        });

        async function runTask(taskType) {
            const loading = document.getElementById(taskType + '-loading');
            const resultsDiv = document.getElementById(taskType + '-results');
            
            loading.classList.add('active');
            resultsDiv.innerHTML = '';

            let serversText = '';
            let params = {};

            switch(taskType) {
                case 'ntp': serversText = document.getElementById('ntp-servers').value; break;
                case 'web': 
                    serversText = document.getElementById('web-servers').value;
                    params.action = document.getElementById('web-action').value;
                    break;
                case 'cloud':
                    serversText = document.getElementById('cloud-servers').value;
                    params.action = document.getElementById('cloud-action').value;
                    break;
                case 'version': serversText = document.getElementById('version-servers').value; break;
                case 'archive':
                    serversText = document.getElementById('archive-servers').value;
                    params.stream_type = document.getElementById('archive-stream').value;
                    break;
                case 'db': serversText = document.getElementById('db-servers').value; break;
                case 'pos':
                    serversText = document.getElementById('pos-servers').value;
                    params.folder = document.getElementById('pos-folder').value;
                    break;
                case 'ip':
                    serversText = document.getElementById('ip-servers').value;
                    params.interface = document.getElementById('ip-interface').value;
                    break;
            }

            const servers = serversText.split('\\n').filter(s => s.trim());
            
            try {
                const response = await fetch('/api/run_task', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({task: taskType, servers: servers, params: params})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    displayResults(taskType, data.results);
                } else {
                    resultsDiv.innerHTML = '<div class="card" style="background: #f8d7da; color: #721c24;">Ошибка: ' + data.error + '</div>';
                }
            } catch (error) {
                resultsDiv.innerHTML = '<div class="card" style="background: #f8d7da; color: #721c24;">Ошибка запроса: ' + error.message + '</div>';
            } finally {
                loading.classList.remove('active');
            }
        }

        function displayResults(taskType, results) {
            const resultsDiv = document.getElementById(taskType + '-results');
            
            if (!results || results.length === 0) {
                resultsDiv.innerHTML = '<div class="card">Нет результатов</div>';
                return;
            }

            let html = '<table class="results-table"><thead><tr>';
            
            // Headers based on task type
            html += '<th>Сервер</th><th>Статус</th><th>Результат</th>';
            if (taskType === 'ntp') html += '<th>Текущее</th><th>Ожидаемое</th>';
            if (taskType === 'version') html += '<th>Версия</th>';
            if (taskType === 'archive') html += '<th>Дней</th>';
            if (taskType === 'db') html += '<th>Размер</th>';
            if (taskType === 'pos') html += '<th>Кол-во терминалов</th>';
            if (taskType === 'ip') html += '<th>IP адрес</th>';
            
            html += '</tr></thead><tbody>';

            results.forEach(r => {
                const statusClass = r.success ? 'status-success' : 'status-error';
                const statusText = r.success ? '✓ OK' : '✗ Ошибка';
                
                html += `<tr>
                    <td>${r.server}</td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td>${r.status}</td>`;
                
                if (taskType === 'ntp') html += `<td>${r.current || '-'}</td><td>${r.expected || '-'}</td>`;
                if (taskType === 'version') html += `<td>${r.version || '-'}</td>`;
                if (taskType === 'archive') html += `<td>${r.days || '-'}</td>`;
                if (taskType === 'db') html += `<td>${r.size || '-'}</td>`;
                if (taskType === 'pos') html += `<td>${r.count || 0}</td>`;
                if (taskType === 'ip') html += `<td>${r.ip || '-'}</td>`;
                
                html += '</tr>';
            });

            html += '</tbody></table>';
            
            // Export button
            html += '<div style="margin-top: 20px;"><button class="btn btn-success" onclick="exportToExcel(\'' + taskType + '\')">📊 Экспорт в Excel</button></div>';
            
            resultsDiv.innerHTML = html;
        }

        function exportToExcel(taskType) {
            window.location.href = '/api/export_excel?task=' + taskType;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/run_task', methods=['POST'])
def run_task_api():
    try:
        data = request.get_json()
        task_type = data.get('task')
        servers = data.get('servers', [])
        params = data.get('params', {})
        
        if not task_type or not servers:
            return jsonify({'success': False, 'error': 'Не указаны задача или серверы'}), 400
        
        results = process_servers(servers, task_type, params)
        
        # Сохраняем результаты для экспорта
        RESULTS_STORE[task_type] = results
        
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        logger.error(f"Ошибка выполнения задачи: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export_excel')
def export_excel():
    try:
        task_type = request.args.get('task')
        if not task_type or task_type not in RESULTS_STORE:
            return jsonify({'success': False, 'error': 'Нет данных для экспорта'}), 400
        
        results = RESULTS_STORE[task_type]
        if not results:
            return jsonify({'success': False, 'error': 'Пустые результаты'}), 400
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Результаты_{task_type}"
        
        # Заголовки
        headers = ['Сервер', 'Статус', 'Результат']
        if task_type == 'ntp': headers.extend(['Текущее', 'Ожидаемое'])
        if task_type == 'version': headers.append('Версия')
        if task_type == 'archive': headers.append('Дней')
        if task_type == 'db': headers.extend(['Статус БД', 'Размер'])
        if task_type == 'pos': headers.append('Кол-во терминалов')
        if task_type == 'ip': headers.append('IP адрес')
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = FONT_BOLD
            cell.fill = FILL_GREEN
            cell.alignment = CENTER_ALIGN
        
        # Данные
        for row_idx, result in enumerate(results, 2):
            ws.cell(row=row_idx, column=1, value=result['server'])
            ws.cell(row=row_idx, column=2, value='OK' if result['success'] else 'Ошибка')
            ws.cell(row=row_idx, column=3, value=result.get('status', ''))
            
            col_offset = 4
            if task_type == 'ntp':
                ws.cell(row=row_idx, column=col_offset, value=result.get('current', ''))
                ws.cell(row=row_idx, column=col_offset+1, value=result.get('expected', ''))
            elif task_type == 'version':
                ws.cell(row=row_idx, column=col_offset, value=result.get('version', ''))
            elif task_type == 'archive':
                ws.cell(row=row_idx, column=col_offset, value=result.get('days', ''))
            elif task_type == 'db':
                ws.cell(row=row_idx, column=col_offset, value=result.get('status', ''))
                ws.cell(row=row_idx, column=col_offset+1, value=result.get('size', ''))
            elif task_type == 'pos':
                ws.cell(row=row_idx, column=col_offset, value=result.get('count', 0))
            elif task_type == 'ip':
                ws.cell(row=row_idx, column=col_offset, value=result.get('ip', ''))
            
            # Раскраска
            status_cell = ws.cell(row=row_idx, column=2)
            if result['success']:
                status_cell.fill = FILL_GREEN
            else:
                status_cell.fill = FILL_RED
        
        # Автоширина колонок
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        filename = f"BK_{task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(base_path, filename)
        wb.save(filepath)
        
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        logger.error(f"Ошибка экспорта Excel: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 BK Server Manager - Современный Веб-Интерфейс")
    print("=" * 60)
    print("📱 Откройте в браузере: http://localhost:5000")
    print("🛑 Для остановки нажмите Ctrl+C")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
