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

def update_cloudflare_kv(new_link, match_name):
    """Cập nhật nội dung M3U mới trực tiếp vào Cloudflare KV Storage"""
    clean_link = new_link.replace('\\', '').replace('"', '').replace("'", "").strip()
    
    # Đọc các biến cấu hình KV từ môi trường (Đã thay tên biến cho đúng bản chất)
    cf_account_id = os.getenv('CF_ACCOUNT_ID')
    cf_kv_namespace_id = os.getenv('CF_KV_NAMESPACE_ID')
    cf_api_token = os.getenv('CF_API_TOKEN')
    
    # Tên của key lưu trữ file m3u trong KV (ví dụ: 'm3u_content')
    kv_key_name = 'playlist' 

# 1. Lấy dữ liệu cũ và đưa về dạng danh sách các dòng (bỏ dòng trống thừa)
    raw_content = get_current_worker_content()
    
    # Tách thành từng dòng, loại bỏ khoảng trắng thừa ở đầu/cuối mỗi dòng và lọc bỏ dòng trống hoàn toàn
    lines = [line.strip() for line in raw_content.split('\n') if line.strip()]
    
  # Định nghĩa các dòng cấu hình IPTV (Loại bỏ \n ở dòng cuối cùng)
    vlc_options = (
        '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36\n'
        '#EXTVLCOPT:http-referrer=https://bunchatv4.net/\n'
        '#EXTVLCOPT:http-origin=https://bunchatv4.net'  # Dòng cuối không để \n ở đây nữa
    )
    
    # Tạo cụm text hoàn chỉnh cho trận đấu mới (Nối mạch thẳng xuống clean_link)
    new_entry = f'#EXTINF:-1 group-title="LIVE" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/1/1a/Canal%2B_Sport_2015.png", {match_name}\n{vlc_options}\n{clean_link}'
    
    # XỬ LÝ CHÈN LÊN ĐẦU KHÔNG DÒNG TRỐNG:
    if lines and lines[0].startswith("#EXTM3U"):
        header = lines[0]  # Dòng đầu tiên cố định: #EXTM3U url-tvg="..."
        
        if len(lines) > 1:
            # Gộp lại các dòng kênh cũ, nối nhau bằng đúng 1 dấu xuống dòng \n
            old_channels = "\n".join(lines[1:])
            # Ghép mạch liên tục: Header -> Trận mới -> Kênh cũ
            playlist = f"{header}\n{new_entry}\n{old_channels}"
        else:
            playlist = f"{header}\n{new_entry}"
    else:
        default_header = '#EXTM3U url-tvg="https://vnepg.site/epg.xml"'
        if lines:
            old_channels = "\n".join(lines)
            playlist = f"{default_header}\n{new_entry}\n{old_channels}"
        else:
            playlist = f"{default_header}\n{new_entry}"
            
    # 2. Đường dẫn API chính thức của Cloudflare để ghi đè (PUT) giá trị của một KEY trong KV
    url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/storage/kv/namespaces/{cf_kv_namespace_id}/values/{kv_key_name}"
    
    # Headers xác thực API Token
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "text/plain" # Gửi dữ liệu dạng văn bản thô (M3U) lên KV
    }

    try:
        # 3. Gửi PUT request để đẩy trực tiếp chuỗi M3U lên Cloudflare KV
        res = requests.put(url, headers=headers, data=playlist.encode('utf-8'), timeout=15)
        
        # Cloudflare API thành công khi trả về kết quả có "success": true trong JSON
        if res.status_code == 200 and res.json().get("success") == True:
            print(f"✅ Đã cập nhật thành công trận {match_name} vào Cloudflare KV!")
            send_telegram(f"✅ Cloudflare KV Updated!\n⚽ {match_name}\n🔗 {clean_link}")
        else:
            error_msg = res.json().get("errors", [{}])[0].get("message", "Lỗi không xác định")
            print(f"❌ Lỗi API Cloudflare: {res.status_code} - {error_msg}")
            send_telegram(f"❌ Lỗi Cloudflare KV: {res.status_code}\n{error_msg[:100]}")
            
    except Exception as e:
        print(f"❌ Lỗi kết nối khi update KV: {e}")
        send_telegram(f"❌ Lỗi kết nối cập nhật KV: {str(e)[:100]}")

if __name__ == "__main__":
    print("🚀 Bắt đầu test script...")
    
    # 1. Lấy dữ liệu do bạn nhập từ giao diện GitHub truyền xuống
    url_tran_dau = os.getenv('MATCH_URL')
    ten_tran_dau = os.getenv('MATCH_NAME')
    
    # Kiểm tra xem người dùng có nhập thiếu dữ liệu không
    if not url_tran_dau or not ten_tran_dau:
        print("❌ Lỗi: Thiếu dữ liệu MATCH_URL hoặc MATCH_NAME từ GitHub Actions!")
    else:
        # 2. GỌI HÀM chạy (Tuyệt đối không viết chữ "def" ở đây nữa)
        update_cloudflare_kv(url_tran_dau, ten_tran_dau)
