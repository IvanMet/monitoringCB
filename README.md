# 🔐 Password Generator with GUI

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

## 📌 About the Project

**Password Generator with GUI** is an application for securely creating, analyzing, and storing strong passwords. The program allows you to generate passwords with customizable parameters, evaluate their strength, and store encrypted passwords in a local database.

### 🎯 Project Goal

Develop a secure password generation application with an intuitive graphical user interface.

### ✅ Features / Tasks

- Generate passwords with customizable parameters (length, character types)
- Password strength assessment (entropy, vulnerability checks)
- Secure encrypted password storage
- Data export and import
- Simple and user-friendly graphical interface

---

## 🚀 Features

| Feature | Description |
|---------|-------------|
| 🔄 **Password Generation** | Customizable length, uppercase/lowercase letters, digits, special characters |
| 🛡️ **Strength Analysis** | Entropy calculation, weak password detection, improvement recommendations |
| 💾 **Storage** | Encrypted password storage in SQLite database |
| 📤 **Export/Import** | Export passwords to JSON/CSV, import from files |
| 📋 **Copy to Clipboard** | One-click copy generated password |
| 🔍 **Search** | Quick search through saved passwords |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-------------|
| Programming Language | **Python 3.12+** |
| GUI Framework | **Tkinter / PyQt 6** |
| Cryptography | **cryptography** (Fernet, PBKDF2) |
| Database | **SQLite 3** |
| Additional Libraries | `secrets`, `string`, `re`, `base64` |

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/password-generator.git
cd password-generator
