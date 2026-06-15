#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Мониторинг курсов валют ЦБ РФ
Версия: 1.0
Автор: Student
Описание: Программа отслеживает курсы валют с сайта ЦБ РФ,
сохраняет историю в базу данных, строит графики и отправляет уведомления.
"""

import requests
import sqlite3
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import statistics
import os
import time

# ==================== КОНФИГУРАЦИЯ ====================

# Список отслеживаемых валют (код: название)
CURRENCIES = {
    'USD': 'Доллар США',
    'EUR': 'Евро',
    'CNY': 'Китайский юань',
    'GBP': 'Фунт стерлингов',
    'JPY': 'Японская иена'
}

# URL API ЦБ РФ (JSON формат)
CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

# Настройки базы данных
DB_NAME = "exchange_rates.db"

# Настройки уведомлений (для Telegram - опционально)
TELEGRAM_BOT_TOKEN = None  # Вставьте токен для включения уведомлений
TELEGRAM_CHAT_ID = None  # Вставьте chat_id для включения уведомлений

# Пороги для уведомлений (в рублях)
THRESHOLDS = {
    'USD': 100.0,
    'EUR': 105.0,
    'CNY': 14.0
}

# Процент изменения для срочного уведомления
ALERT_PERCENT_CHANGE = 2.0

# Настройка русских шрифтов для графиков
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


# ==================== КЛАСС ДЛЯ РАБОТЫ С API ====================

class CurrencyParser:
    """Класс для получения курсов валют с сайта ЦБ РФ"""

    def __init__(self):
        self.url = CBR_URL
        self.last_update = None
        self.rates_cache = None

    def fetch_rates(self) -> Optional[Dict[str, float]]:
        """
        Получает актуальные курсы валют

        Returns:
            Словарь {код_валюты: курс} или None при ошибке
        """
        try:
            # Отправляем запрос к API
            print("🔄 Загрузка курсов валют...")
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()

            # Парсим JSON ответ
            data = response.json()
            self.last_update = datetime.now()

            # Извлекаем курсы только нужных нам валют
            rates = {}
            for currency_code in CURRENCIES.keys():
                if currency_code in data['Valute']:
                    rate = data['Valute'][currency_code]['Value']
                    rates[currency_code] = rate
                else:
                    print(f"⚠️ Валюта {currency_code} не найдена")

            self.rates_cache = rates
            print(f"✅ Загружено {len(rates)} курсов валют")
            return rates

        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка соединения: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return None
        except Exception as e:
            print(f"❌ Неизвестная ошибка: {e}")
            return None

    def display_rates(self, rates: Dict[str, float]) -> str:
        """Форматирует курсы для красивого вывода"""
        if not rates:
            return "Нет данных о курсах"

        result = "\n" + "=" * 55 + "\n"
        result += f"📊 КУРСЫ ВАЛЮТ НА {self.last_update.strftime('%d.%m.%Y %H:%M:%S')}\n"
        result += "=" * 55 + "\n\n"

        for code, rate in rates.items():
            name = CURRENCIES[code]
            result += f"💵 {name} ({code}): {rate:.2f} ₽\n"

        result += "\n" + "=" * 55 + "\n"
        result += f"📅 Обновлено: {self.last_update.strftime('%d.%m.%Y %H:%M:%S')}\n"
        result += f"🏦 Источник: Центральный Банк РФ\n"

        return result


# ==================== КЛАСС ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ====================

class Database:
    """Класс для работы с SQLite базой данных"""

    def __init__(self):
        self.db_name = DB_NAME
        self.init_database()

    def init_database(self):
        """Создает таблицы если их нет"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Таблица для хранения курсов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                currency_code TEXT NOT NULL,
                rate REAL NOT NULL,
                UNIQUE(date, currency_code)
            )
        ''')

        # Индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON exchange_rates(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_currency ON exchange_rates(currency_code)')

        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")

    def save_rates(self, rates: Dict[str, float]):
        """Сохраняет курсы в базу данных"""
        date = datetime.now().strftime('%Y-%m-%d')
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        saved = 0
        for currency_code, rate in rates.items():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO exchange_rates (date, currency_code, rate)
                    VALUES (?, ?, ?)
                ''', (date, currency_code, rate))
                saved += 1
            except sqlite3.Error as e:
                print(f"⚠️ Ошибка сохранения {currency_code}: {e}")

        conn.commit()
        conn.close()
        print(f"✅ Сохранено {saved} курсов за {date}")

    def get_history(self, currency_code: str, days: int = 30) -> List[Tuple[str, float]]:
        """Получает историю курса за последние N дней"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT date, rate 
            FROM exchange_rates 
            WHERE currency_code = ? AND date >= ?
            ORDER BY date ASC
        ''', (currency_code, start_date))

        history = cursor.fetchall()
        conn.close()
        return history

    def get_latest_rate(self, currency_code: str) -> Optional[Tuple[str, float]]:
        """Получает последний сохраненный курс"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT date, rate 
            FROM exchange_rates 
            WHERE currency_code = ?
            ORDER BY date DESC LIMIT 1
        ''', (currency_code,))

        result = cursor.fetchone()
        conn.close()
        return result


# ==================== КЛАСС ДЛЯ АНАЛИТИКИ ====================

class Analytics:
    """Класс для анализа курсов валют"""

    def __init__(self):
        self.db = Database()

    def calculate_change(self, currency_code: str, days: int = 1) -> Optional[Dict]:
        """Рассчитывает изменение курса за период"""
        history = self.db.get_history(currency_code, days + 1)

        if len(history) < 2:
            return None

        old_date, old_rate = history[0]
        new_date, new_rate = history[-1]

        absolute_change = new_rate - old_rate
        percent_change = (absolute_change / old_rate) * 100

        return {
            'currency': currency_code,
            'old_rate': old_rate,
            'new_rate': new_rate,
            'old_date': old_date,
            'new_date': new_date,
            'absolute_change': absolute_change,
            'percent_change': percent_change,
            'trend': '📈 растет' if percent_change > 0 else '📉 падает' if percent_change < 0 else '➡️ стабилен'
        }

    def get_statistics(self, currency_code: str, days: int = 30) -> Dict:
        """Получает статистику по курсу за период"""
        history = self.db.get_history(currency_code, days)

        if not history:
            return {'error': f'Нет данных по {currency_code}'}

        rates = [rate for _, rate in history]

        return {
            'currency': currency_code,
            'period_days': days,
            'min_rate': min(rates),
            'max_rate': max(rates),
            'avg_rate': statistics.mean(rates),
            'median_rate': statistics.median(rates),
            'volatility': statistics.stdev(rates) if len(rates) > 1 else 0,
            'start_rate': rates[0],
            'end_rate': rates[-1],
            'total_change': rates[-1] - rates[0],
            'total_change_percent': ((rates[-1] - rates[0]) / rates[0]) * 100
        }

    def simple_prediction(self, currency_code: str, days_ahead: int = 5) -> Optional[float]:
        """Простой прогноз на основе среднего изменения"""
        history = self.db.get_history(currency_code, 30)

        if len(history) < 7:
            return None

        # Используем последние 7 дней для прогноза
        rates = [rate for _, rate in history[-7:]]
        changes = [rates[i] - rates[i - 1] for i in range(1, len(rates))]

        if not changes:
            return None

        avg_daily_change = statistics.mean(changes)
        last_rate = rates[-1]
        predicted_rate = last_rate + (avg_daily_change * days_ahead)

        return max(0, predicted_rate)

    def check_alerts(self, current_rates: Dict[str, float]) -> List[str]:
        """Проверяет нужно ли отправить уведомления"""
        alerts = []

        for currency_code, current_rate in current_rates.items():
            # Проверка порогов
            if currency_code in THRESHOLDS:
                threshold = THRESHOLDS[currency_code]
                if current_rate > threshold:
                    alerts.append(
                        f"⚠️ {currency_code} превысил {threshold} ₽! "
                        f"Текущий курс: {current_rate:.2f} ₽"
                    )

            # Проверка резких изменений
            change = self.calculate_change(currency_code, 1)
            if change and abs(change['percent_change']) > ALERT_PERCENT_CHANGE:
                alerts.append(
                    f"🚨 {currency_code} резко {'вырос' if change['percent_change'] > 0 else 'упал'} "
                    f"на {abs(change['percent_change']):.2f}%! "
                    f"Текущий курс: {change['new_rate']:.2f} ₽"
                )

        return alerts


# ==================== КЛАСС ДЛЯ ВИЗУАЛИЗАЦИИ ====================

class Visualizer:
    """Класс для построения графиков"""

    def __init__(self):
        self.db = Database()

    def plot_currency_trend(self, currency_code: str, days: int = 30, save_file: str = None):
        """Строит график курса валюты"""
        history = self.db.get_history(currency_code, days)

        if not history:
            print(f"❌ Нет данных для {currency_code}")
            return

        # Подготовка данных
        dates = [datetime.strptime(date, '%Y-%m-%d') for date, _ in history]
        rates = [rate for _, rate in history]

        # Создание графика
        fig, ax = plt.subplots(figsize=(12, 6))

        # Основная линия
        ax.plot(dates, rates, marker='o', linewidth=2, markersize=4,
                color='blue', label=f'{currency_code} курс')

        # Скользящее среднее
        if len(rates) >= 7:
            ma_rates = []
            for i in range(len(rates)):
                start = max(0, i - 6)
                window = rates[start:i + 1]
                ma_rates.append(sum(window) / len(window))
            ax.plot(dates, ma_rates, '--', linewidth=1.5, color='red',
                    label='Скользящее среднее (7 дней)')

        # Настройки
        ax.set_xlabel('Дата', fontsize=12)
        ax.set_ylabel('Курс (₽)', fontsize=12)
        ax.set_title(f'Динамика курса {currency_code} ({CURRENCIES[currency_code]})\n'
                     f'за последние {days} дней', fontsize=14, fontweight='bold')

        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='best')

        # Форматирование дат
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
        plt.xticks(rotation=45)

        # Аннотации минимума и максимума
        min_idx = rates.index(min(rates))
        max_idx = rates.index(max(rates))

        ax.annotate(f'Мин: {rates[min_idx]:.2f}₽',
                    xy=(dates[min_idx], rates[min_idx]),
                    xytext=(10, -20), textcoords='offset points',
                    arrowprops=dict(arrowstyle='->', color='green'))

        ax.annotate(f'Макс: {rates[max_idx]:.2f}₽',
                    xy=(dates[max_idx], rates[max_idx]),
                    xytext=(10, 10), textcoords='offset points',
                    arrowprops=dict(arrowstyle='->', color='red'))

        plt.tight_layout()

        if save_file:
            plt.savefig(save_file, dpi=100, bbox_inches='tight')
            print(f"✅ График сохранен в {save_file}")
        else:
            plt.show()

    def plot_multiple_currencies(self, currencies: List[str], days: int = 30, save_file: str = None):
        """Строит сравнительный график нескольких валют"""
        fig, ax = plt.subplots(figsize=(14, 7))

        colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']

        for i, currency_code in enumerate(currencies):
            history = self.db.get_history(currency_code, days)

            if not history:
                print(f"⚠️ Нет данных для {currency_code}")
                continue

            dates = [datetime.strptime(date, '%Y-%m-%d') for date, _ in history]
            rates = [rate for _, rate in history]
            color = colors[i % len(colors)]

            ax.plot(dates, rates, marker='.', linewidth=2, color=color,
                    label=f'{currency_code} - {CURRENCIES[currency_code]}')

        ax.set_xlabel('Дата', fontsize=12)
        ax.set_ylabel('Курс (₽)', fontsize=12)
        ax.set_title(f'Сравнение курсов валют за последние {days} дней',
                     fontsize=14, fontweight='bold')

        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='best')

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
        plt.xticks(rotation=45)

        plt.tight_layout()

        if save_file:
            plt.savefig(save_file, dpi=100, bbox_inches='tight')
            print(f"✅ График сохранен в {save_file}")
        else:
            plt.show()


# ==================== КЛАСС ДЛЯ УВЕДОМЛЕНИЙ (опционально) ====================

class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram"""

    def __init__(self):
        self.enabled = TELEGRAM_BOT_TOKEN is not None and TELEGRAM_CHAT_ID is not None

        if self.enabled:
            try:
                # Пытаемся импортировать telegram бота
                from telegram import Bot
                self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
                self.chat_id = TELEGRAM_CHAT_ID
                print("✅ Telegram уведомления включены")
            except ImportError:
                print("⚠️ Библиотека python-telegram-bot не установлена")
                self.enabled = False
            except Exception as e:
                print(f"⚠️ Ошибка настройки Telegram: {e}")
                self.enabled = False
        else:
            print("ℹ️ Telegram уведомления отключены (токен не задан)")

    def send_message(self, message: str):
        """Отправляет сообщение"""
        if not self.enabled:
            return

        try:
            from telegram import Bot
            import asyncio

            async def send():
                await self.bot.send_message(chat_id=self.chat_id, text=message)

            asyncio.run(send())
            print("✅ Уведомление отправлено в Telegram")
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")

    def send_alerts(self, alerts: List[str]):
        """Отправляет несколько уведомлений"""
        if not alerts:
            return

        message = "🔔 <b>Уведомления мониторинга валют</b>\n\n"
        message += "\n".join(f"• {alert}" for alert in alerts)
        self.send_message(message)


# ==================== ГЛАВНЫЙ КЛАСС ПРИЛОЖЕНИЯ ====================

class CurrencyMonitor:
    """Главный класс приложения"""

    def __init__(self):
        self.parser = CurrencyParser()
        self.db = Database()
        self.analytics = Analytics()
        self.visualizer = Visualizer()
        self.notifier = TelegramNotifier()
        self.last_rates = None

    def update(self) -> Optional[Dict[str, float]]:
        """Обновляет курсы и сохраняет в БД"""
        print("\n" + "=" * 60)
        print(f"🔄 ОБНОВЛЕНИЕ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        rates = self.parser.fetch_rates()

        if rates:
            self.db.save_rates(rates)
            self.last_rates = rates

            # Проверка уведомлений
            alerts = self.analytics.check_alerts(rates)
            if alerts:
                self.notifier.send_alerts(alerts)

            return rates
        else:
            print("❌ Не удалось получить курсы")
            return None

    def show_current(self):
        """Показывает текущие курсы"""
        rates = self.update()
        if rates:
            print(self.parser.display_rates(rates))

    def show_daily_report(self):
        """Показывает ежедневный отчет"""
        print("\n" + "=" * 60)
        print(f"📊 ЕЖЕДНЕВНЫЙ ОТЧЕТ - {datetime.now().strftime('%d.%m.%Y')}")
        print("=" * 60)

        if not self.last_rates:
            print("Сначала обновите курсы (опция 1)")
            return

        for code, rate in self.last_rates.items():
            print(f"\n💵 {CURRENCIES[code]} ({code})")
            print(f"   Текущий курс: {rate:.2f} ₽")

            # Изменение за день
            change = self.analytics.calculate_change(code, 1)
            if change:
                sign = "+" if change['percent_change'] > 0 else ""
                print(f"   📈 Изменение за день: {sign}{change['percent_change']:.2f}%")
                print(f"   {change['trend']}")

            # Статистика за месяц
            stats = self.analytics.get_statistics(code, 30)
            if 'error' not in stats:
                print(f"   📊 Мин/макс за месяц: {stats['min_rate']:.2f} / {stats['max_rate']:.2f} ₽")
                print(f"   📉 Волатильность: {stats['volatility']:.3f}")

            # Прогноз
            pred = self.analytics.simple_prediction(code, 5)
            if pred:
                print(f"   🔮 Прогноз через 5 дней: {pred:.2f} ₽")

        print("\n" + "=" * 60)

    def generate_all_charts(self):
        """Генерирует все графики"""
        print("\n📊 Генерация графиков...")

        # Индивидуальные графики для каждой валюты
        for code in CURRENCIES.keys():
            filename = f"{code}_trend_30d.png"
            self.visualizer.plot_currency_trend(code, days=30, save_file=filename)

        # Сравнительный график
        self.visualizer.plot_multiple_currencies(
            list(CURRENCIES.keys())[:4],
            days=30,
            save_file="currencies_compare.png"
        )

        print("\n✅ Все графики сгенерированы!")

    def show_statistics(self):
        """Показывает подробную статистику"""
        print("\n" + "=" * 60)
        print("📈 ПОДРОБНАЯ СТАТИСТИКА ЗА 30 ДНЕЙ")
        print("=" * 60)

        for code in CURRENCIES.keys():
            stats = self.analytics.get_statistics(code, 30)
            if 'error' not in stats:
                print(f"\n💵 {CURRENCIES[code]} ({code}):")
                print(f"   Минимальный курс: {stats['min_rate']:.2f} ₽")
                print(f"   Максимальный курс: {stats['max_rate']:.2f} ₽")
                print(f"   Средний курс: {stats['avg_rate']:.2f} ₽")
                print(f"   Изменение за месяц: {stats['total_change_percent']:+.2f}%")
                print(f"   Волатильность: {stats['volatility']:.3f}")


# ==================== ФУНКЦИЯ ЗАПУСКА ====================

def print_menu():
    """Выводит меню программы"""
    print("\n" + "=" * 50)
    print("        МОНИТОРИНГ КУРСОВ ВАЛЮТ ЦБ РФ")
    print("=" * 50)
    print("1. 📊 Показать текущие курсы")
    print("2. 📈 Показать ежедневный отчет")
    print("3. 📉 Показать статистику за 30 дней")
    print("4. 📊 Построить все графики")
    print("5. 🔄 Обновить данные")
    print("6. ℹ️ Информация о программе")
    print("0. 🚪 Выход")
    print("=" * 50)


def show_info():
    """Показывает информацию о программе"""
    print("\n" + "=" * 60)
    print("ℹ️ ИНФОРМАЦИЯ О ПРОГРАММЕ")
    print("=" * 60)
    print("\nНазвание: Мониторинг курсов валют ЦБ РФ")
    print("Версия: 1.0")
    print("\nФункции:")
    print("  • Получение курсов с сайта ЦБ РФ")
    print("  • Сохранение истории в базу данных SQLite")
    print("  • Анализ динамики и статистика")
    print("  • Построение графиков")
    print("  • Прогнозирование курса")
    print("  • Уведомления при резких изменениях")
    print("\nИсточник данных: https://www.cbr-xml-daily.ru/")
    print("\nСовет: Запускайте программу ежедневно для набора истории")
    print("=" * 60)


def main():
    """Главная функция программы"""
    monitor = CurrencyMonitor()

    print("""
    ╔══════════════════════════════════════════════════╗
    ║     МОНИТОРИНГ КУРСОВ ВАЛЮТ ЦБ РФ                ║
    ║          Учебный проект по Python                ║
    ╚══════════════════════════════════════════════════╝
    """)

    while True:
        print_menu()
        choice = input("\nВыберите действие (0-6): ").strip()

        if choice == "0":
            print("\n👋 До свидания! Хорошего дня!")
            break

        elif choice == "1":
            monitor.show_current()

        elif choice == "2":
            monitor.show_daily_report()

        elif choice == "3":
            monitor.show_statistics()

        elif choice == "4":
            monitor.generate_all_charts()

        elif choice == "5":
            print("\n🔄 Принудительное обновление...")
            monitor.update()

        elif choice == "6":
            show_info()

        else:
            print("\n❌ Неверный выбор! Попробуйте снова.")

        input("\nНажмите Enter для продолжения...")


# ==================== ТОЧКА ВХОДА ====================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Программа прервана пользователем. До свидания!")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        print("Пожалуйста, проверьте подключение к интернету и попробуйте снова.")
        input("\nНажмите Enter для выхода...")