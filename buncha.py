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

    # 1. Lấy dữ liệu M3U cũ đang có từ KV (Sử dụng hàm get_current_worker_content đã sửa ở câu trước)
    current_content = get_current_worker_content()
    
    # Định nghĩa các dòng option cấu hình VLC / IPTV Player
    vlc_options = (
        '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36\n'
        '#EXTVLCOPT:http-referrer=https://bunchatv4.net/\n'
        '#EXTVLCOPT:http-origin=https://bunchatv4.net'
    )
    
    # Tạo entry trận đấu mới
    new_entry = f'\n#EXTINF:-1 group-title="LIVE" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/1/1a/Canal%2B_Sport_2015.png", {match_name}\n{vlc_options}\n{clean_link}'
    
        # XỬ LÝ ĐẨY LÊN ĐẦU:
        # Nếu file cũ đã có nội dung và bắt đầu bằng #EXTM3U
        if current_content.startswith("#EXTM3U"):
            # Tách dòng đầu tiên (#EXTM3U...) ra khỏi phần danh sách kênh cũ
            lines = current_content.split('\n', 1)
            header = lines[0] # Đây là dòng '#EXTM3U url-tvg="..."'
            
            if len(lines) > 1:
                old_channels = lines[1] # Toàn bộ các trận đấu cũ trước đây
                # Nối theo thứ tự: Dòng đầu -> Trận mới -> Các trận cũ
                playlist = f"{header}\n{new_entry}\n{old_channels}"
            else:
                # Nếu file cũ mới chỉ có mỗi dòng header chưa có kênh nào
                playlist = f"{header}\n{new_entry}"
        else:
            # Trường hợp khẩn cấp nếu file cũ bị lỗi không có header #EXTM3U
            playlist = f'#EXTM3U url-tvg="https://vnepg.site/epg.xml"\n{new_entry}\n{current_content}'

    # 2. Đường dẫn API chính thức của Cloudflare để ghi đè (PUT) giá trị của một KEY trong KV
    url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/storage/kv/namespaces/{cf_kv_namespace_id}/values/{kv_key_name}"
    
    # Headers xác thực API Token
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "text/plain" # Gửi dữ liệu dạng văn bản thô (M3U) lên KV
    }

    try:
        # 3. Gửi PUT request để đẩy trực tiếp chuỗi M3U lên Cloudflare KV
        res = requests.put(url, headers=headers, data=updated_m3u.encode('utf-8'), timeout=15)
        
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
