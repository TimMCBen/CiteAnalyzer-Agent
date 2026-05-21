# -*- coding: utf-8 -*-
"""
该模块提供一个统一的配置管理器。

它负责从项目根目录的 `config.json` 文件中加载所有配置，
并提供按模块（如 crawler, filtering）获取配置的方法。
"""

import json
from pathlib import Path
import logging

class ConfigManager:
    _instance = None
    _config_data = {}
    _config_path = Path("config.json")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """
        从 config.json 加载配置。
        如果文件不存在或解析失败，将记录错误并使用空配置。
        """
        if self._config_path.exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config_data = json.load(f)
                logging.info(f"已从 {self._config_path} 加载配置。")
            except json.JSONDecodeError:
                logging.error(f"{self._config_path} 文件格式错误，配置加载失败。")
                self._config_data = {}
        else:
            logging.warning(f"{self._config_path} 文件不存在，将使用默认或空配置。")
            self._config_data = {}

    def get_config(self, section: str):
        """
        获取指定模块（section）的配置。

        Args:
            section (str): 配置中的顶级键，如 'crawler' 或 'filtering'。

        Returns:
            dict: 对应模块的配置字典，如果不存在则返回空字典。
        """
        return self._config_data.get(section, {})

    def save_config(self, new_config_data: dict):
        """
        将新的配置数据保存到 config.json 文件并重新加载。
        """
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config_data, f, ensure_ascii=False, indent=2)
            logging.info(f"配置已成功保存到 {self._config_path}")
            self.reload_config()
            return True
        except Exception as e:
            logging.error(f"保存配置到 {self._config_path} 时失败: {e}")
            return False

    def reload_config(self):
        """重新从文件加载配置。"""
        self.load_config()

# 创建一个单例实例，方便在项目中任何地方导入和使用
config_manager = ConfigManager()
