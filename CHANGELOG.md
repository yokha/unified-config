# **Changelog**

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


---

## **[v0.1.1] - 2025-03-17**
### 🔥 Enhancements & Documentation Update  
This release includes an updated **README.md** and a new **video tutorial**.

#### ✅ **Added**
- **Updated README.md** with installation steps and improved documentation.
- **Changelog updated** to reflect new changes.

#### 📝 **Notes**
- Video tutorial is hosted and linked in the documentation.

---

## **[v0.1.0] - 2025-03-16**
### 🎉 First Release!  
The initial release of **unified-config**.

#### ✅ **Added**
- **Core Configuration Manager** with support for:
  - **Database storage (PostgreSQL, MySQL, SQLite)**
  - **Redis caching and pub/sub support**
  - **File-based fallback support (YAML, JSON, TOML)**
- **Automatic Configuration Sync** between database and Redis.
- **Exponential Backoff Retry Mechanism** for handling database transaction failures.
- **Bulk Configuration Updates** with atomic operations.
- **Flexible Query Timeout Handling** with per-query settings.

#### 📝 **Notes**
- Published to **TestPyPI** and **PyPI**.
- License: **MIT**.
- Installation and package verification tests added.

---

### **Legend**
- **`Added`**: New features introduced in this version.
- **`Fixed`**: Bugs resolved in this version.
- **`Notes`**: Additional details or metadata related to the release.

---

[🔙 Return to README](./README.md)
