#!/usr/bin/env python3
"""
Test script để kiểm tra streamlit-image-comparison đã được cài đặt chưa
"""

import sys

def test_imports():
    """Test các import cần thiết"""
    tests = {
        "streamlit": False,
        "PIL (Pillow)": False,
        "streamlit_image_comparison": False
    }
    
    # Test streamlit
    try:
        import streamlit
        tests["streamlit"] = True
        print(f"✅ streamlit: {streamlit.__version__}")
    except ImportError:
        print("❌ streamlit: Chưa cài đặt")
    
    # Test PIL
    try:
        from PIL import Image
        import PIL
        tests["PIL (Pillow)"] = True
        print(f"✅ PIL (Pillow): {PIL.__version__}")
    except ImportError:
        print("❌ PIL (Pillow): Chưa cài đặt")
    
    # Test streamlit-image-comparison
    try:
        from streamlit_image_comparison import image_comparison
        tests["streamlit_image_comparison"] = True
        print("✅ streamlit-image-comparison: Đã cài đặt")
    except ImportError:
        print("❌ streamlit-image-comparison: Chưa cài đặt")
        print("   Chạy: pip install streamlit-image-comparison")
    
    print("\n" + "="*50)
    
    # Summary
    all_passed = all(tests.values())
    if all_passed:
        print("🎉 Tất cả dependencies đã sẵn sàng!")
        print("Bạn có thể chạy: streamlit run app.py")
        return 0
    else:
        print("⚠️  Một số dependencies còn thiếu:")
        for name, status in tests.items():
            if not status:
                print(f"   - {name}")
        print("\nChạy lệnh sau để cài đặt:")
        print("   pip install streamlit-image-comparison")
        return 1

if __name__ == "__main__":
    print("🔍 Kiểm tra dependencies cho Before/After Slider...")
    print("="*50)
    sys.exit(test_imports())
