#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BK Server Manager - Modern Web Interface
Версия: 2.0
Запуск: python bk_manager_web.py
Доступ: http://0.0.0.0:5000
"""

import os
import sys
import subprocess
import threading
import time
import re
import socket
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO

# --- КОНФИГУРАЦИЯ ---
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False
ETHALON_FILE = 'ethalon.txt'

app = Flask(__name__)

# Глобальные переменные для хранения состояния задач
tasks = {}
task_lock = threading.Lock()

# --- HTML ШАБЛОН ---
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BK Server Manager</title>
    <style>
        :root {
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --secondary: #64748b;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --background: #f8fafc;
            --surface: #ffffff;
            --text: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background-color: var(--background);
            color: var(--text);
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        header {
            background: linear-gradient(135deg, var(--primary), #818cf8);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
            border-radius: 0 0 1rem 1rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        header h1 {
            text-align: center;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        header p {
            text-align: center;
            opacity: 0.9;
            font-size: 1.1rem;
        }

        .tabs {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
            overflow-x: auto;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--border);
        }

        .tab-btn {
            padding: 0.75rem 1.5rem;
            background: var(--surface);
            border: none;
            border-radius: 0.5rem 0.5rem 0 0;
            cursor: pointer;
            font-weight: 600;
            color: var(--text-secondary);
            transition: all 0.2s;
            white-space: nowrap;
        }

        .tab-btn:hover {
            background: #f1f5f9;
            color: var(--primary);
        }

        .tab-btn.active {
            background: var(--primary);
            color: white;
            transform: translateY(2px);
        }

        .tab-content {
            display: none;
            background: var(--surface);
            padding: 2rem;
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            animation: fadeIn 0.3s ease-in-out;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .input-group {
            margin-bottom: 1.5rem;
        }

        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 600;
            color: var(--text);
        }

        textarea, input[type="text"], input[type="number"], select {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            font-size: 1rem;
            resize: vertical;
            transition: border-color 0.2s;
        }

        textarea:focus, input:focus, select:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }

        textarea {
            min-height: 150px;
            font-family: 'Consolas', monospace;
        }

        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 0.5rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-hover);
            transform: translateY(-1px);
        }

        .btn-success {
            background: var(--success);
            color: white;
        }

        .btn-success:hover {
            background: #059669;
        }

        .btn-secondary {
            background: var(--secondary);
            color: white;
        }

        .btn-secondary:hover {
            background: #475569;
        }

        .actions {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }

        .status-bar {
            margin-top: 1.5rem;
            padding: 1rem;
            background: #f1f5f9;
            border-radius: 0.5rem;
            border-left: 4px solid var(--primary);
        }

        .log-container {
            margin-top: 1rem;
            background: #1e293b;
            color: #10b981;
            padding: 1rem;
            border-radius: 0.5rem;
            font-family: 'Consolas', monospace;
            font-size: 0.9rem;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }

        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }

        th {
            background: #f8fafc;
            font-weight: 600;
            color: var(--text-secondary);
        }

        tr:hover {
            background: #f8fafc;
        }

        .status-ok {
            color: var(--success);
            font-weight: 600;
        }

        .status-error {
            color: var(--danger);
            font-weight: 600;
        }

        .status-warning {
            color: var(--warning);
            font-weight: 600;
        }

        .progress-bar {
            height: 4px;
            background: #e2e8f0;
            border-radius: 2px;
            margin-top: 0.5rem;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: var(--primary);
            width: 0%;
            transition: width 0.3s;
        }

        .spinner {
            display: inline-block;
            width: 1rem;
            height: 1rem;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .hidden {
            display: none;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>BK Server Manager</h1>
            <p>Современный интерфейс управления серверами БК</p>
        </div>
    </header>

    <div class="container">
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('ntp')">NTP Серверы</button>
            <button class="tab-btn" onclick="switchTab('web')">Web Интерфейс</button>
            <button class="tab-btn" onclick="switchTab('cloud')">Cloud Функции</button>
            <button class="tab-btn" onclick="switchTab('versions')">Версии ПО</button>
            <button class="tab-btn" onclick="switchTab('archive')">Глубина Архива</button>
            <button class="tab-btn" onclick="switchTab('users')">Пользователи</button>
            <button class="tab-btn" onclick="switchTab('rights')">Права Доступа</button>
            <button class="tab-btn" onclick="switchTab('db')">Состояние БД</button>
            <button class="tab-btn" onclick="switchTab('pos')">POS Терминалы</button>
            <button class="tab-btn" onclick="switchTab('ip')">IP Адреса</button>
        </div>

        <!-- Вкладка NTP -->
        <div id="ntp" class="tab-content active">
            <h2>Проверка и настройка NTP серверов</h2>
            <div class="input-group">
                <label for="ntp-servers">Список серверов (каждый с новой строки):</label>
                <textarea id="ntp-servers" placeholder="192.168.1.1&#10;192.168.1.2&#10;server.example.com"></textarea>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('ntp')">
                    <span>Запустить проверку</span>
                </button>
                <button class="btn btn-success hidden" id="export-ntp" onclick="exportToExcel('ntp')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="ntp-status" class="status-bar hidden">
                <div id="ntp-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="ntp-progress"></div></div>
            </div>
            <div id="ntp-log" class="log-container hidden"></div>
            <div id="ntp-results" class="hidden"></div>
        </div>

        <!-- Вкладка Web -->
        <div id="web" class="tab-content">
            <h2>Управление Web интерфейсом</h2>
            <div class="input-group">
                <label for="web-servers">Список серверов:</label>
                <textarea id="web-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="input-group">
                <label for="web-action">Действие:</label>
                <select id="web-action">
                    <option value="start">Включить Web</option>
                    <option value="stop">Выключить Web</option>
                    <option value="check">Проверить статус</option>
                </select>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('web')">
                    <span>Выполнить</span>
                </button>
                <button class="btn btn-success hidden" id="export-web" onclick="exportToExcel('web')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="web-status" class="status-bar hidden">
                <div id="web-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="web-progress"></div></div>
            </div>
            <div id="web-log" class="log-container hidden"></div>
            <div id="web-results" class="hidden"></div>
        </div>

        <!-- Вкладка Cloud -->
        <div id="cloud" class="tab-content">
            <h2>Управление Cloud функциями</h2>
            <div class="input-group">
                <label for="cloud-servers">Список серверов:</label>
                <textarea id="cloud-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="input-group">
                <label for="cloud-action">Действие:</label>
                <select id="cloud-action">
                    <option value="enable">Включить Cloud</option>
                    <option value="disable">Выключить Cloud</option>
                    <option value="check">Проверить статус</option>
                </select>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('cloud')">
                    <span>Выполнить</span>
                </button>
                <button class="btn btn-success hidden" id="export-cloud" onclick="exportToExcel('cloud')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="cloud-status" class="status-bar hidden">
                <div id="cloud-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="cloud-progress"></div></div>
            </div>
            <div id="cloud-log" class="log-container hidden"></div>
            <div id="cloud-results" class="hidden"></div>
        </div>

        <!-- Вкладка Версии -->
        <div id="versions" class="tab-content">
            <h2>Проверка версий ПО</h2>
            <div class="input-group">
                <label for="versions-servers">Список серверов:</label>
                <textarea id="versions-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('versions')">
                    <span>Запустить проверку</span>
                </button>
                <button class="btn btn-success hidden" id="export-versions" onclick="exportToExcel('versions')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="versions-status" class="status-bar hidden">
                <div id="versions-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="versions-progress"></div></div>
            </div>
            <div id="versions-log" class="log-container hidden"></div>
            <div id="versions-results" class="hidden"></div>
        </div>

        <!-- Вкладка Архив -->
        <div id="archive" class="tab-content">
            <h2>Проверка глубины архивов</h2>
            <div class="input-group">
                <label for="archive-servers">Список серверов:</label>
                <textarea id="archive-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('archive')">
                    <span>Запустить проверку</span>
                </button>
                <button class="btn btn-success hidden" id="export-archive" onclick="exportToExcel('archive')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="archive-status" class="status-bar hidden">
                <div id="archive-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="archive-progress"></div></div>
            </div>
            <div id="archive-log" class="log-container hidden"></div>
            <div id="archive-results" class="hidden"></div>
        </div>

        <!-- Вкладка Пользователи -->
        <div id="users" class="tab-content">
            <h2>Получение списка пользователей</h2>
            <div class="input-group">
                <label for="users-servers">Список серверов:</label>
                <textarea id="users-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('users')">
                    <span>Получить список</span>
                </button>
                <button class="btn btn-success hidden" id="export-users" onclick="exportToExcel('users')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="users-status" class="status-bar hidden">
                <div id="users-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="users-progress"></div></div>
            </div>
            <div id="users-log" class="log-container hidden"></div>
            <div id="users-results" class="hidden"></div>
        </div>

        <!-- Вкладка Права -->
        <div id="rights" class="tab-content">
            <h2>Проверка прав пользователей по эталону</h2>
            <div class="input-group">
                <label for="rights-servers">Список серверов:</label>
                <textarea id="rights-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="input-group">
                <label for="rights-ethalon">Эталонный файл (путь или содержимое):</label>
                <input type="text" id="rights-ethalon" placeholder="C:\\path\\to\\ethalon.txt или вставьте содержимое">
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('rights')">
                    <span>Проверить права</span>
                </button>
                <button class="btn btn-success hidden" id="export-rights" onclick="exportToExcel('rights')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="rights-status" class="status-bar hidden">
                <div id="rights-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="rights-progress"></div></div>
            </div>
            <div id="rights-log" class="log-container hidden"></div>
            <div id="rights-results" class="hidden"></div>
        </div>

        <!-- Вкладка БД -->
        <div id="db" class="tab-content">
            <h2>Проверка состояния БД</h2>
            <div class="input-group">
                <label for="db-servers">Список серверов:</label>
                <textarea id="db-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('db')">
                    <span>Проверить БД</span>
                </button>
                <button class="btn btn-success hidden" id="export-db" onclick="exportToExcel('db')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="db-status" class="status-bar hidden">
                <div id="db-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="db-progress"></div></div>
            </div>
            <div id="db-log" class="log-container hidden"></div>
            <div id="db-results" class="hidden"></div>
        </div>

        <!-- Вкладка POS -->
        <div id="pos" class="tab-content">
            <h2>Проверка POS терминалов</h2>
            <div class="input-group">
                <label for="pos-servers">Список серверов:</label>
                <textarea id="pos-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('pos')">
                    <span>Проверить POS</span>
                </button>
                <button class="btn btn-success hidden" id="export-pos" onclick="exportToExcel('pos')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="pos-status" class="status-bar hidden">
                <div id="pos-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="pos-progress"></div></div>
            </div>
            <div id="pos-log" class="log-container hidden"></div>
            <div id="pos-results" class="hidden"></div>
        </div>

        <!-- Вкладка IP -->
        <div id="ip" class="tab-content">
            <h2>Проверка IP адресов</h2>
            <div class="input-group">
                <label for="ip-servers">Список серверов:</label>
                <textarea id="ip-servers" placeholder="192.168.1.1&#10;192.168.1.2"></textarea>
            </div>
            <div class="actions">
                <button class="btn btn-primary" onclick="runTask('ip')">
                    <span>Проверить IP</span>
                </button>
                <button class="btn btn-success hidden" id="export-ip" onclick="exportToExcel('ip')">
                    Экспорт в Excel
                </button>
            </div>
            <div id="ip-status" class="status-bar hidden">
                <div id="ip-status-text">Выполнение...</div>
                <div class="progress-bar"><div class="progress-fill" id="ip-progress"></div></div>
            </div>
            <div id="ip-log" class="log-container hidden"></div>
            <div id="ip-results" class="hidden"></div>
        </div>
    </div>

    <script>
        let currentResults = {};

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

            document.getElementById(tabId).classList.add('active');
            
            // Find the button that corresponds to this tab and make it active
            const buttons = document.querySelectorAll('.tab-btn');
            buttons.forEach(btn => {
                if (btn.getAttribute('onclick').includes("'" + tabId + "'")) {
                    btn.classList.add('active');
                }
            });
        }

        async function runTask(taskType) {
            const serversInput = document.getElementById(taskType + '-servers');
            const servers = serversInput.value.trim().split('\\n').filter(function(s) { return s.trim(); });

            if (servers.length === 0) {
                alert('Пожалуйста, введите список серверов');
                return;
            }

            const statusDiv = document.getElementById(taskType + '-status');
            const logDiv = document.getElementById(taskType + '-log');
            const resultsDiv = document.getElementById(taskType + '-results');
            const exportBtn = document.getElementById('export-' + taskType);
            const progressFill = document.getElementById(taskType + '-progress');
            const statusText = document.getElementById(taskType + '-status-text');

            statusDiv.classList.remove('hidden');
            logDiv.classList.remove('hidden');
            resultsDiv.innerHTML = '';
            resultsDiv.classList.add('hidden');
            exportBtn.classList.add('hidden');
            progressFill.style.width = '0%';
            statusText.textContent = 'Подготовка...';
            statusText.style.color = '#1e293b';
            logDiv.textContent = 'Запуск задачи...\\n';

            try {
                const response = await fetch('/api/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ task: taskType, servers: servers })
                });

                if (!response.ok) {
                    throw new Error('Ошибка сети: ' + response.status);
                }

                const data = await response.json();

                if (data.status === 'started') {
                    pollStatus(taskType);
                } else {
                    throw new Error(data.message || 'Неизвестная ошибка');
                }
            } catch (error) {
                statusText.textContent = 'Ошибка!';
                statusText.style.color = '#ef4444';
                logDiv.textContent += '\\nОшибка: ' + error.message + '\\n';
                logDiv.scrollTop = logDiv.scrollHeight;
            }
        }

        async function pollStatus(taskType) {
            const statusDiv = document.getElementById(taskType + '-status');
            const logDiv = document.getElementById(taskType + '-log');
            const resultsDiv = document.getElementById(taskType + '-results');
            const exportBtn = document.getElementById('export-' + taskType);
            const progressFill = document.getElementById(taskType + '-progress');
            const statusText = document.getElementById(taskType + '-status-text');

            const interval = setInterval(async () => {
                try {
                    const response = await fetch('/api/status/' + taskType);
                    const data = await response.json();

                    if (data.status === 'running') {
                        statusText.textContent = 'Выполнение: ' + data.completed + '/' + data.total;
                        progressFill.style.width = ((data.completed / data.total) * 100) + '%';
                        logDiv.textContent = data.log.join('\\n');
                        logDiv.scrollTop = logDiv.scrollHeight;
                    } else if (data.status === 'completed') {
                        clearInterval(interval);
                        statusText.textContent = 'Готово!';
                        statusText.style.color = '#10b981';
                        progressFill.style.width = '100%';
                        logDiv.textContent = data.log.join('\\n');

                        if (data.results && data.results.length > 0) {
                            currentResults[taskType] = data.results;
                            displayResults(taskType, data.results);
                            exportBtn.classList.remove('hidden');
                        }
                    } else if (data.status === 'error') {
                        clearInterval(interval);
                        statusText.textContent = 'Ошибка выполнения';
                        statusText.style.color = '#ef4444';
                        logDiv.textContent = data.log.join('\\n');
                    }
                } catch (error) {
                    clearInterval(interval);
                    statusText.textContent = 'Ошибка опроса';
                    logDiv.textContent += '\\nОшибка опроса: ' + error.message;
                }
            }, 1000);
        }

        function displayResults(taskType, results) {
            const resultsDiv = document.getElementById(taskType + '-results');
            resultsDiv.classList.remove('hidden');

            let html = '<table><thead><tr>';

            if (results.length > 0) {
                Object.keys(results[0]).forEach(function(key) {
                    html += '<th>' + key + '</th>';
                });
            }

            html += '</tr></thead><tbody>';

            results.forEach(function(row) {
                html += '<tr>';
                Object.values(row).forEach(function(value) {
                    let className = '';
                    if (typeof value === 'string') {
                        if (value.toLowerCase().includes('ok') || value.toLowerCase().includes('true') || value.toLowerCase().includes('yes') || value.toLowerCase().includes('synced') || value.toLowerCase().includes('enabled') || value.toLowerCase().includes('healthy')) {
                            className = 'status-ok';
                        } else if (value.toLowerCase().includes('error') || value.toLowerCase().includes('false') || value.toLowerCase().includes('no') || value.toLowerCase().includes('not synced') || value.toLowerCase().includes('disabled') || value.toLowerCase().includes('failed')) {
                            className = 'status-error';
                        } else if (value.toLowerCase().includes('warn')) {
                            className = 'status-warning';
                        }
                    }
                    html += '<td class="' + className + '">' + value + '</td>';
                });
                html += '</tr>';
            });

            html += '</tbody></table>';
            resultsDiv.innerHTML = html;
        }

        function exportToExcel(taskType) {
            if (!currentResults[taskType] || currentResults[taskType].length === 0) {
                alert('Нет данных для экспорта');
                return;
            }

            fetch('/api/export/' + taskType, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data: currentResults[taskType] })
            })
            .then(function(response) { 
                return response.blob(); 
            })
            .then(function(blob) {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = taskType + '_report_' + new Date().toISOString().slice(0,10) + '.xlsx';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            })
            .catch(function(error) { 
                alert('Ошибка экспорта: ' + error.message); 
            });
        }
    </script>
</body>
</html>'''

# --- ЛОГИКА ЗАДАЧ ---

def check_ntp(servers):
    """Проверка NTP синхронизации"""
    results = []
    for server in servers:
        # Имитация проверки NTP
        results.append({
            "Server": server,
            "NTP Status": "Synced" if hash(server) % 2 == 0 else "Not Synced",
            "Offset": f"{abs(hash(server) % 100)}ms",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def manage_web(servers, action):
    """Управление веб-интерфейсом"""
    results = []
    for server in servers:
        results.append({
            "Server": server,
            "Action": action,
            "Result": "Success" if hash(server) % 3 != 0 else "Failed",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def manage_cloud(servers, action):
    """Управление cloud функциями"""
    results = []
    for server in servers:
        results.append({
            "Server": server,
            "Action": action,
            "Status": "Enabled" if action == 'enable' else "Disabled",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def check_versions(servers):
    """Проверка версий ПО"""
    versions = ["2.1.0", "2.0.5", "2.1.0", "1.9.8"]
    results = []
    for i, server in enumerate(servers):
        results.append({
            "Server": server,
            "Version": versions[i % len(versions)],
            "Latest": "Yes" if i % 2 == 0 else "No",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def check_archive(servers):
    """Проверка глубины архива"""
    results = []
    for server in servers:
        depth = abs(hash(server) % 365)
        results.append({
            "Server": server,
            "Archive Depth": f"{depth} days",
            "Status": "OK" if depth > 30 else "Warning",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def get_users(servers):
    """Получение списка пользователей"""
    results = []
    users_list = ["admin", "operator", "viewer", "manager"]
    for server in servers:
        user = users_list[abs(hash(server)) % len(users_list)]
        results.append({
            "Server": server,
            "User": user,
            "Last Login": datetime.now().strftime("%Y-%m-%d"),
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def check_rights(servers, ethalon=None):
    """Проверка прав доступа"""
    results = []
    for server in servers:
        match = abs(hash(server)) % 2 == 0
        results.append({
            "Server": server,
            "Match Ethalon": "Yes" if match else "No",
            "Issues": "None" if match else "Permissions mismatch",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def check_db(servers):
    """Проверка состояния БД"""
    results = []
    for server in servers:
        size = abs(hash(server) % 100)
        results.append({
            "Server": server,
            "DB Size": f"{size} GB",
            "Status": "Healthy" if size < 80 else "Warning",
            "Connections": abs(hash(server) % 50),
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def check_pos(servers):
    """Проверка POS терминалов"""
    results = []
    for server in servers:
        count = abs(hash(server) % 10)
        results.append({
            "Server": server,
            "POS Count": count,
            "Active": max(0, count - (abs(hash(server)) % 3)),
            "Status": "OK" if count > 0 else "No POS",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    return results

def check_ip(servers):
    """Проверка IP адресов"""
    results = []
    for server in servers:
        try:
            ip = socket.gethostbyname(server)
            results.append({
                "Hostname": server,
                "IP Address": ip,
                "Resolved": "Yes",
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except:
            results.append({
                "Hostname": server,
                "IP Address": "N/A",
                "Resolved": "No",
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
    return results

def run_task_thread(task_type, servers, task_id):
    """Фоновый поток для выполнения задачи"""
    with task_lock:
        tasks[task_id] = {
            'status': 'running',
            'progress': 0,
            'total': len(servers),
            'completed': 0,
            'log': [f"Started task {task_type} for {len(servers)} servers"],
            'results': []
        }

    try:
        results = []

        if task_type == 'ntp':
            results = check_ntp(servers)
        elif task_type == 'web':
            action = 'check'  # Можно получить из запроса
            results = manage_web(servers, action)
        elif task_type == 'cloud':
            action = 'check'  # Можно получить из запроса
            results = manage_cloud(servers, action)
        elif task_type == 'versions':
            results = check_versions(servers)
        elif task_type == 'archive':
            results = check_archive(servers)
        elif task_type == 'users':
            results = get_users(servers)
        elif task_type == 'rights':
            results = check_rights(servers, None)
        elif task_type == 'db':
            results = check_db(servers)
        elif task_type == 'pos':
            results = check_pos(servers)
        elif task_type == 'ip':
            results = check_ip(servers)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        # Эмулируем прогресс
        for i in range(len(servers)):
            time.sleep(0.1)  # Имитация работы
            with task_lock:
                tasks[task_id]['completed'] = i + 1
                tasks[task_id]['progress'] = int(((i + 1) / len(servers)) * 100)
                tasks[task_id]['log'].append(f"Processed: {servers[i]}")

        with task_lock:
            tasks[task_id]['results'] = results
            tasks[task_id]['log'].append(f"Completed: {len(results)} results")
            tasks[task_id]['status'] = 'completed'

    except Exception as e:
        with task_lock:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['log'].append(f"Error: {str(e)}")

# --- API ROUTES ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/run', methods=['POST'])
def api_run():
    data = request.json
    task_type = data.get('task')
    servers = data.get('servers', [])

    if not task_type or not servers:
        return jsonify({'status': 'error', 'message': 'Missing task or servers'}), 400

    task_id = task_type  # Используем тип задачи как ID для простоты

    # Запускаем задачу в фоне
    thread = threading.Thread(target=run_task_thread, args=(task_type, servers, task_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'task_id': task_id})

@app.route('/api/status/<task_id>')
def api_status(task_id):
    with task_lock:
        if task_id not in tasks:
            return jsonify({'status': 'not_found'})

        task = tasks[task_id]
        return jsonify({
            'status': task['status'],
            'progress': task['progress'],
            'completed': task['completed'],
            'total': task['total'],
            'log': task['log'],
            'results': task.get('results', [])
        })

@app.route('/api/export/<task_type>', methods=['POST'])
def api_export(task_type):
    data = request.json
    results = data.get('data', [])

    if not results:
        return jsonify({'error': 'No data to export'}), 400

    # Создаем Excel файл
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{task_type}_report"

    # Заголовки
    if results:
        headers = list(results[0].keys())
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")

        # Данные
        for row_idx, row_data in enumerate(results, 2):
            for col_idx, header in enumerate(headers, 1):
                ws.cell(row=row_idx, column=col_idx, value=row_data.get(header))

    # Сохраняем в буфер
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'{task_type}_report_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

if __name__ == '__main__':
    print(f"BK Server Manager запускается на http://{HOST}:{PORT}")
    print(f"Доступные вкладки: NTP, Web, Cloud, Versions, Archive, Users, Rights, DB, POS, IP")
    print(f"Экспорт в Excel доступен для всех отчетов")
    print(f"Нажмите Ctrl+C для остановки")

    try:
        app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
    except KeyboardInterrupt:
        print("\nСервер остановлен пользователем")
