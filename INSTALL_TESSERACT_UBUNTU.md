# Installing Tesseract OCR on Ubuntu

The `pytesseract` library requires the Tesseract OCR engine to be installed on your system. This guide will help you install it on Ubuntu.

## Installation Steps

### 1. Update package list
```bash
sudo apt update
```

### 2. Install Tesseract OCR
```bash
sudo apt install tesseract-ocr
```

### 3. Install language data (optional but recommended)
For English support (usually included by default):
```bash
sudo apt install tesseract-ocr-eng
```

For additional languages:
```bash
# List available languages
apt search tesseract-ocr

# Install specific language (example for Hindi)
sudo apt install tesseract-ocr-hin
```

### 4. Verify installation
```bash
tesseract --version
```

You should see output like:
```
tesseract 4.1.1
 leptonica-1.78.0
  libgif 5.1.4 : libjpeg 8d (libjpeg-turbo 2.0.3) : libpng 1.6.37 : libtiff 4.1.0 : zlib 1.2.11 : libwebp 0.6.1
```

### 5. Check Tesseract location
```bash
which tesseract
```

Usually located at: `/usr/bin/tesseract`

## If Tesseract is in a non-standard location

If Tesseract is installed but not in your PATH, you can configure pytesseract to use a specific path:

### Option 1: Add to PATH
Add to your `~/.bashrc` or `~/.profile`:
```bash
export PATH=$PATH:/path/to/tesseract
```

### Option 2: Configure in Python code
You can specify the tesseract path in your code:
```python
import pytesseract

# Set tesseract path (if not in PATH)
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
```

## For Docker/Container deployments

If deploying in Docker, add to your Dockerfile:
```dockerfile
RUN apt-get update && \
    apt-get install -y tesseract-ocr tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*
```

## Testing

Test that it works:
```bash
# Test from command line
echo "Hello World" > test.txt
tesseract test.txt output
cat output.txt
```

## Troubleshooting

### Error: "tesseract is not installed or it's not in your PATH"
1. Verify installation: `which tesseract`
2. Check if it's executable: `ls -la /usr/bin/tesseract`
3. Try running directly: `tesseract --version`
4. If installed but not found, add to PATH or configure path in code

### Error: "Failed loading language"
- Install the required language pack
- Check available languages: `tesseract --list-langs`

### Permission errors
- Ensure tesseract is executable: `sudo chmod +x /usr/bin/tesseract`
- Check file permissions if saving images

