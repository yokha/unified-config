# **Contributing to Unified Config**

Thank you for your interest in contributing to Unified Config! We welcome contributions from everyone. By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## **Ways to Contribute**
- **Report Bugs**: Found an issue? Let us know by creating a [bug report](https://github.com/yokha/unified-config/issues/new?template=bug_report.md).
- **Suggest Features**: Have an idea for improvement? Share it by submitting a [feature request](https://github.com/yokha/unified-config/issues/new?template=feature_request.md).
- **Fix Issues**: Browse our [issue tracker](https://github.com/yokha/unified-config/issues) and help resolve open issues.
- **Improve Documentation**: Correct typos, enhance clarity, or add missing details to make our documentation better.
- **Submit Code**: Implement new features, fix bugs, or improve performance by contributing code.

---

## **Getting Started**

### **1. Fork the Repository**
Click the **"Fork"** button at the top right of this repository to create your copy.

### **2. Clone the Repository**
```bash
git clone https://github.com/<your-username>/unified-config.git
cd unified-config
```

### **3. Set Up the Development Environment**
- Ensure you have Python 3.8+ installed.
- Set up a virtual environment using Makefile:
  ```bash
  make setup-venv
  ```
- Install dependencies using Poetry:
  ```bash
  make update-requirements
  ```

### **4. Create a Branch**
Use a descriptive name for your branch:
```bash
git checkout -b feature/your-feature-name
```

### **5. Make Changes**
- Write clean, readable, and well-documented code.
- Ensure your changes adhere to the project's coding style.

### **6. Run Tests**
- Make sure all tests pass:
  ```bash
  make unit-test
  make integration-test
  ```

### **7. Commit Your Changes**
Write clear and concise commit messages:
```bash
git add .
git commit -m "Add feature: your feature name"
```

### **8. Push to Your Fork**
```bash
git push origin feature/your-feature-name
```

### **9. Create a Pull Request**
- Go to the original repository and click **"New Pull Request"**.
- Provide a detailed description of your changes.
- Link any related issues or discussions.

---

## **Code Guidelines**

### **1. Code Style**
- Follow [PEP 8](https://pep8.org/) for Python code.
- Use `black` for code formatting:
  ```bash
  make format
  ```
- Run linting:
  ```bash
  make lint
  ```

### **2. Testing**
- Write tests for new features or bug fixes.
- Use `pytest` for unit and integration tests.

### **3. Documentation**
- Update or add to the documentation if your changes affect the public API.

---

## **Testbench (Example Applications)**
Unified Config includes **example applications** under `testbench/`, showcasing a **FastAPI backend** and **Angular frontend** for configuration management.

#### **Running Testbench Services**
```bash
cd testbench
make docker-up  # Start the example backend services using Docker Compose
make migrate-upgrade  # Apply migrations for the example FastAPI backend
make run  # Start the example FastAPI backend
```

---

## **Need Help?**
If you have questions or need assistance:
- Open a [discussion](https://github.com/yokha/unified-config/discussions).
- Reach out via [GitHub issues](https://github.com/yokha/unified-config/issues).

---

Thank you for contributing to Unified Config and helping make it better! 😊

---

[🔙 Return to README](./README.md)

