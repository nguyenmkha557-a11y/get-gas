import os
import subprocess
import requests  # Đã thêm thư viện này để không bị lỗi sập code

def send_telegram(message):
    token = os.getenv('TG_TOKEN')
    chat_id = os.getenv('TG_CHAT_ID')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        try:
            res = requests.post(url, data=data, timeout=10)
            if res.status_code == 200:
                print("✅ Đã gửi thông báo Telegram thành công")
            else:
                print(f"❌ Telegram trả về mã lỗi: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"❌ Lỗi kết nối khi gửi Telegram: {e}")
    else:
        print("⚠️ Thiếu TG_TOKEN hoặc TG_CHAT_ID trong biến môi trường, không thể gửi Telegram")

def get_current_worker_content():
    """Lấy nội dung M3U hiện tại từ Cloudflare Worker"""
    # Lưu ý: Hãy đảm bảo URL này trả về chuỗi có chứa chữ "#EXTM3U"
    url = "https://iptv-api.nguyenmkha557.workers.dev/playlist.json"
    try:
        res = requests.get(url, timeout=10)
        print(f"ℹ️ Kết quả tải Worker: Status {res.status_code}")
        
        if res.status_code == 200 and "#EXTM3U" in res.text:
            print("✅ Đã lấy thành công nội dung M3U từ Worker")
            return res.text.strip()
        else:
            print("⚠️ URL chạy thành công nhưng nội dung trả về không chứa từ khóa '#EXTM3U'")
    except Exception as e:
        print(f"❌ Lỗi khi kết nối tới Cloudflare Worker: {e}")
        
    print("ℹ️ Sử dụng chuỗi M3U mặc định.")
    return '#EXTM3U url-tvg="https://vnepg.site/epg.xml"'

if __name__ == "__main__":
    print("🚀 Bắt đầu test script...")
    # Chạy hàm lấy nội dung từ worker
    content = get_current_worker_content()
    
    # Gửi thử một thông báo test về Telegram của bạn để kiểm tra xem Token/Chat ID đúng chưa
    #send_telegram("🔔 Hệ thống test GitHub Actions: Đã kích hoạt script thành công!")
