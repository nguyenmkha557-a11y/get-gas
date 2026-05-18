import os
import time
import requests  # Thư viện xử lý HTTP đồng bộ
from playwright.sync_api import sync_playwright  # Dùng bản đồng bộ (sync)

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
    
    cf_account_id = os.getenv('CF_ACCOUNT_ID')
    cf_kv_namespace_id = os.getenv('CF_KV_NAMESPACE_ID')
    cf_api_token = os.getenv('CF_API_TOKEN')
    kv_key_name = 'playlist' 

    # 1. Lấy dữ liệu cũ và đưa về dạng danh sách các dòng
    raw_content = get_current_worker_content()
    lines = [line.strip() for line in raw_content.split('\n') if line.strip()]
    
    # Định nghĩa các dòng cấu hình IPTV
    vlc_options = (
        '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36\n'
        '#EXTVLCOPT:http-referrer=https://bunchatv4.net/\n'
        '#EXTVLCOPT:http-origin=https://bunchatv4.net'
    )
    
    # Tạo cụm text hoàn chỉnh cho trận đấu mới
    new_entry = f'#EXTINF:-1 group-title="LIVE" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/1/1a/Canal%2B_Sport_2015.png", {match_name}\n{vlc_options}\n{clean_link}'
    
    # XỬ LÝ CHÈN LÊN ĐẦU KHÔNG DÒNG TRỐNG:
    if lines and lines[0].startswith("#EXTM3U"):
        header = lines[0]
        if len(lines) > 1:
            old_channels = "\n".join(lines[1:])
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
            
    # 2. Đường dẫn API chính thức của Cloudflare
    url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/storage/kv/namespaces/{cf_kv_namespace_id}/values/{kv_key_name}"
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "text/plain"
    }

    try:
        # 3. Gửi PUT request để đẩy trực tiếp chuỗi M3U lên Cloudflare KV
        res = requests.put(url, headers=headers, data=playlist.encode('utf-8'), timeout=15)
        
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


def sniff_m3u8(url):
    """HÀM ĐỒNG BỘ: Sử dụng Playwright sync để quét bắt link m3u8 từ trang web"""
    with sync_playwright() as p:
        # Mở trình duyệt ẩn (headless=True) thích hợp cho GitHub Actions
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        found_links = []

        # Lắng nghe các request mạng để "bắt" link .m3u8
        def handle_request(request):
            if ".m3u8" in request.url or "playlist" in request.url:
                if request.url not in found_links:
                    print(f"[+] Đã bắt được link: {request.url}")
                    found_links.append(request.url)

        page.on("request", handle_request)

        print(f"[*] Đang tải trang: {url}")
        try:
            # Truy cập trang và đợi mạng rảnh (networkidle) tối đa 60 giây
            page.goto(url, wait_until="networkidle", timeout=60000)
            # Dùng time.sleep đồng bộ thay vì asyncio.sleep
            time.sleep(5) 
            
        except Exception as e:
            print(f"[-] Có cảnh báo/lỗi trong khi load trang: {e}")
        
        browser.close()
        return found_links


if __name__ == "__main__":
    print("🚀 Bắt đầu chạy script đồng bộ...")
    
    # 1. Lấy dữ liệu MATCH_URL và MATCH_NAME từ GitHub Actions truyền xuống
    url_tran_dau = os.getenv('MATCH_URL')
    ten_tran_dau = os.getenv('MATCH_NAME')
    
    if not url_tran_dau or not ten_tran_dau:
        print("❌ Lỗi: Thiếu dữ liệu MATCH_URL hoặc MATCH_NAME từ biến môi trường!")
    else:
        # 2. Gọi hàm đồng bộ quét link trực tiếp
        print(f"🔍 Bắt đầu quét link stream cho trận đấu: {ten_tran_dau}")
        links = sniff_m3u8(url_tran_dau)
        
        if links:
            # Lấy link đầu tiên tìm thấy để cập nhật
            stream_link = links[0]
            print(f"🎯 Chọn link đầu tiên để chèn: {stream_link}")
            
            # 3. Gọi hàm cập nhật lên Cloudflare KV
            update_cloudflare_kv(stream_link, ten_tran_dau)
        else:
            print("❌ Không bắt được link m3u8 nào từ URL này. Không tiến hành cập nhật KV.")
            send_telegram(f"❌ Thất bại: Không tìm thấy link m3u8 cho trận: {ten_tran_dau}")
