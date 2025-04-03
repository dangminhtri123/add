import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
from PIL import Image
import threading
import json
import os
import requests
import re
import base64
import openpyxl
import uuid
from selenium import webdriver

# ---------------------------
# PHẦN ĐĂNG NHẬP (Login)
# ---------------------------

def load_key_from_file():
    """Đọc key đã lưu từ file (nếu có)."""
    try:
        with open("key.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return ""

def save_key_to_file(key):
    """Ghi key vào file."""
    try:
        with open("key.txt", "w") as f:
            f.write(key)
    except Exception as e:
        print("Lỗi khi lưu key:", e)

def get_mac_address():
    """Lấy địa chỉ MAC của máy."""
    mac_num = hex(uuid.getnode()).replace("0x", "").upper()
    mac = ":".join(mac_num[i:i+2] for i in range(0, len(mac_num), 2))
    return mac

def copy_to_clipboard(text, window):
    """Copy text vào clipboard."""
    window.clipboard_clear()
    window.clipboard_append(text)
    window.update()

def check_key(window=None):
    """Hàm kiểm tra key bằng cách gọi API."""
    key = key_entry.get().strip()
    if not key:
        messagebox.showerror("Lỗi", "Vui lòng nhập key!")
        return

    # Lấy thời gian hiện tại theo UTC
    current_time = "2025-04-02 07:12:08"  # Thời gian từ hệ thống
    user_login = "dangminhtri123"  # User login từ hệ thống

    url = f"http://14.225.205.195/api.php?key={key}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        login_data = response.json()
    except requests.exceptions.RequestException:
        messagebox.showerror("Lỗi", "Không thể kết nối đến máy chủ API!")
        return
    except json.JSONDecodeError:
        messagebox.showerror("Lỗi", "Dữ liệu API không hợp lệ!")
        return
    except Exception as e:
        messagebox.showerror("Lỗi", f"Lỗi không xác định: {str(e)}")
        return

    # Kiểm tra cấu trúc dữ liệu API
    if not login_data or not isinstance(login_data, dict):
        messagebox.showerror("Lỗi", "Dữ liệu API không hợp lệ!")
        return

    # Kiểm tra key có tồn tại trong response
    if "key" not in login_data:
        messagebox.showerror("Lỗi", "Dữ liệu API thiếu thông tin key!")
        return

    # Kiểm tra key hợp lệ
    if login_data.get("key") != key:
        messagebox.showerror("Lỗi", "Key không hợp lệ!")
        return

    # Kiểm tra địa chỉ MAC
    local_mac = get_mac_address()
    if login_data.get("mac") != local_mac:
        error_msg = (
            "Key sai hoặc đã được đăng nhập tại nơi khác!\n"
            f"MAC hiện tại: {local_mac}\n"
            f"MAC đăng ký: {login_data.get('mac', 'Không có')}"
        )
        messagebox.showerror("Lỗi", error_msg)
        return

    # Kiểm tra trạng thái Active
    if str(login_data.get("Active")).lower() != "yes":
        messagebox.showerror(
            "Lỗi", 
            "Key chưa được kích hoạt!\nVui lòng liên hệ ADMIN để được hỗ trợ!"
        )
        return

    # Thêm thông tin thời gian và user vào login_data
    login_data.update({
        "login_time": current_time,
        "user": user_login
    })

    # Nếu lưu key được chọn, lưu vào file
    if save_key_var.get():
        try:
            save_key_to_file(key)
        except Exception as e:
            messagebox.showwarning(
                "Cảnh báo", 
                f"Không thể lưu key: {str(e)}\nNhưng bạn vẫn có thể tiếp tục sử dụng."
            )

    # Thông báo đăng nhập thành công
    success_msg = (
        "Đăng nhập thành công!\n"
        f"Thời gian: {current_time}\n"
        f"User: {user_login}\n"
        "Cảm ơn bạn đã sử dụng dịch vụ!"
    )
    messagebox.showinfo("Thông báo", success_msg)

    # Ẩn cửa sổ đăng nhập
    if window:
        try:
            window.withdraw()
        except Exception as e:
            print(f"Lỗi khi ẩn cửa sổ đăng nhập: {e}")
            # Không return ở đây vì không phải lỗi nghiêm trọng

    try:
        # Khởi tạo và hiển thị giao diện chính
        app = MainApp(current_time, login_data)
        app.mainloop()
    except Exception as e:
        messagebox.showerror(
            "Lỗi", 
            f"Không thể khởi tạo giao diện chính: {str(e)}"
        )
        if window:
            window.deiconify()  # Hiển thị lại cửa sổ đăng nhập nếu có lỗi



# ---------------------------
# PHẦN GIAO DIỆN CHÍNH (ZaloChecker)
# ---------------------------

# Mặc định ORIGINAL_COOKIE và ORIGINAL_TOKEN là trống
ORIGINAL_COOKIE = ""
ORIGINAL_TOKEN = ""

# Global cấu hình proxy
USE_PROXY = False
PROXIES = []       # Danh sách proxy dạng chuỗi "ip:port:user:pass"
PROXY_INDEX = 0    # Chỉ số proxy hiện tại

def get_next_proxy():
    """Trả về proxy dưới dạng dict cho requests và cập nhật chỉ số vòng lặp."""
    global PROXIES, PROXY_INDEX
    if not PROXIES:
        return None
    proxy_line = PROXIES[PROXY_INDEX]
    PROXY_INDEX = (PROXY_INDEX + 1) % len(PROXIES)
    try:
        ip, port, user, password = proxy_line.split(':')
        proxy_url = f"http://{user}:{password}@{ip}:{port}"
        return {"http": proxy_url, "https": proxy_url}
    except Exception:
        return None

# Cấu hình giao diện chính
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class MainApp(ctk.CTk):
    def __init__(self, login_time, login_data):
        super().__init__()
        self.geometry("1000x600")
        self.title("ZaloChecker v2.0 | HVKDO - Liên hệ: Mr.Huynh 0971.325.870 ")
        self.resizable(False, False)
        self.login_data = login_data
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, height=600, corner_radius=0, fg_color="#1E3A8A")
        self.sidebar.pack(side="left", fill="y")

        logo_label = ctk.CTkLabel(self.sidebar, text="ZaloChecker v2.0", font=("Arial", 18, "bold"), text_color="white")
        logo_label.pack(pady=20)
        logo_1label = ctk.CTkLabel(self.sidebar, text="Max Speed Turbo", font=("Arial", 12), text_color="white")
        logo_1label.place(x=15,y=40)

        self.icons = ["🏠", "🔍", "⚙️", "📞", "👤"]
        self.pages = ["Trang Chủ", "Check Zalo", "Cài Đặt", "Liên hệ", "Tài Khoản"]
        for icon, page in zip(self.icons, self.pages):
            btn = ctk.CTkButton(self.sidebar,
                                text=f"{icon}  {page}",
                                width=180,
                                height=40,
                                corner_radius=10,
                                fg_color="#1E40AF",
                                command=lambda p=page: self.show_page(p))
            btn.pack(pady=10)

        # Thêm label hiển thị thời gian (được lấy từ API login)
        self.content_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="white", width=680, height=600)
        self.content_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.pages_instances = {}  # Lưu lại instance của từng trang để giữ dữ liệu
        self.current_page = None
        self.show_page("Trang Chủ")

    def show_page(self, page_name):
        if self.current_page is not None:
            self.current_page.pack_forget()

        if page_name in self.pages_instances:
            self.current_page = self.pages_instances[page_name]
        else:
            if page_name == "Trang Chủ":
                self.current_page = HomePage(self.content_frame)
            elif page_name == "Check Zalo":
                self.current_page = CheckZaloPage(self.content_frame)
            elif page_name == "Cài Đặt":
                self.current_page = SettingsPage(self.content_frame)
            elif page_name == "Liên hệ":
                self.current_page = LienHePage(self.content_frame)
            elif page_name == "Tài Khoản":
                # Tạo trang Tài Khoản, truyền login_data
                self.current_page = TaiKhoanPage(self.content_frame, self.login_data)
            else:
                self.current_page = DummyPage(self.content_frame, "Unknown")

            self.pages_instances[page_name] = self.current_page

        self.current_page.pack(expand=True, fill="both")


class HomePage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="white")
        # Trang chủ: Nội dung được tạo theo đúng yêu cầu của bạn
        # Title
        title = ctk.CTkLabel(self, text="Cảm ơn bạn đã sử dụng dịch vụ của ", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title.place(x=20, y=20)

        title_link = ctk.CTkLabel(self, text="Học Viện Kinh Doanh Online", 
                                  font=ctk.CTkFont(size=16, weight="bold"), text_color="#0066cc")
        title_link.place(x=280, y=20)

        # Section 1
        section1_title = ctk.CTkLabel(self, text="1.Vì Sao Chọn ", 
                                      font=ctk.CTkFont(size=14, weight="bold"), text_color="black")
        section1_title.place(x=20, y=50)

        section1_title2 = ctk.CTkLabel(self, text="Chúng Tôi", 
                                       font=ctk.CTkFont(size=14, weight="bold"), text_color="#0066cc")
        section1_title2.place(x=125, y=50)

        section1_title3 = ctk.CTkLabel(self, text="?", 
                                       font=ctk.CTkFont(size=16, weight="bold"), text_color="black")
        section1_title3.place(x=205, y=50)

        # Bullet points for section 1
        bullet1 = ctk.CTkLabel(self, text="- Tool dễ sử dụng, nhanh gọn mượt và không yêu cầu quá nhiều về hiệu năng, cấu hình", 
                               font=ctk.CTkFont(size=14), text_color="black")
        bullet1.place(x=20, y=80)

        bullet2 = ctk.CTkLabel(self, text="- Luôn lắng nghe phản hồi ý kiến của khách hàng để tạo ra Tool hoàn chỉnh nhất", 
                               font=ctk.CTkFont(size=14), text_color="black")
        bullet2.place(x=20, y=110)

        bullet3 = ctk.CTkLabel(self, text="- Check được nhiều dạng:", 
                               font=ctk.CTkFont(size=14), text_color="black")
        bullet3.place(x=20, y=140)

        # Status types
        status1 = ctk.CTkLabel(self, text="+ Live", font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CAF50")
        status1.place(x=40, y=170)
        status1_desc = ctk.CTkLabel(self, text="( Có Zalo )", font=ctk.CTkFont(size=14), text_color="black")
        status1_desc.place(x=90, y=170)

        status2 = ctk.CTkLabel(self, text="+ Die", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FF5722")
        status2.place(x=40, y=200)
        status2_desc = ctk.CTkLabel(self, text="( Không Có Zalo )", font=ctk.CTkFont(size=14), text_color="black")
        status2_desc.place(x=90, y=200)

        status3 = ctk.CTkLabel(self, text="+ LOCKED", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFC107")
        status3.place(x=40, y=230)
        status3_desc = ctk.CTkLabel(self, text="( Tài Khoản Khoá )", font=ctk.CTkFont(size=14), text_color="black")
        status3_desc.place(x=120, y=230)

        status4 = ctk.CTkLabel(self, text="+ VHH", font=ctk.CTkFont(size=14, weight="bold"), text_color="#2196F3")
        status4.place(x=40, y=260)
        status4_desc = ctk.CTkLabel(self, text="( Tài Khoản Vô Hiệu Hoá )", font=ctk.CTkFont(size=14), text_color="black")
        status4_desc.place(x=90, y=260)

        # Section 2
        section2_title = ctk.CTkLabel(self, text="2. Bản Cải Tiến Mới ", 
                                      font=ctk.CTkFont(size=14, weight="bold"), text_color="black")
        section2_title.place(x=20, y=290)

        section2_title2 = ctk.CTkLabel(self, text="Có Những Gì?", 
                                       font=ctk.CTkFont(size=14, weight="bold"), text_color="#0066cc")
        section2_title2.place(x=163, y=290)

        # Bullet points for section 2
        bullet4 = ctk.CTkLabel(self, 
                               text="- Dùng AI Giải Captcha tự động thay vì phải dùng bên Khác tiết kiệm chi phí tối đa cho người dùng", 
                               font=ctk.CTkFont(size=14), text_color="black")
        bullet4.place(x=20, y=320)

        bullet4_sub = ctk.CTkLabel(self, 
                                   text="(Do chúng tôi nghiên cứu và phát triển)", 
                                   font=ctk.CTkFont(size=14), text_color="#0066cc")
        bullet4_sub.place(x=40, y=350)

        bullet5 = ctk.CTkLabel(self, 
                               text="- Giao diện đổi mới bắt mắt hơn, tối ưu cho những máy cấu hình thấp", 
                               font=ctk.CTkFont(size=14), text_color="black")
        bullet5.place(x=20, y=380)

        bullet6 = ctk.CTkLabel(self, 
                               text="- Có thể xuất file làm 2 định dạng: ", 
                               font=ctk.CTkFont(size=14), text_color="black")
        bullet6.place(x=20, y=410)

        file_format1 = ctk.CTkLabel(self, text="xlsx", font=ctk.CTkFont(size=14), text_color="#4CAF50")
        file_format1.place(x=250, y=410)

        and_text = ctk.CTkLabel(self, text="và", font=ctk.CTkFont(size=14), text_color="black")
        and_text.place(x=280, y=410)

        file_format2 = ctk.CTkLabel(self, text="txt", font=ctk.CTkFont(size=14), text_color="black")
        file_format2.place(x=300, y=410)

        format_detail1 = ctk.CTkLabel(self, text="( ", font=ctk.CTkFont(size=14), text_color="black")
        format_detail1.place(x=320, y=410)

        format_detail2 = ctk.CTkLabel(self, text="Excel", font=ctk.CTkFont(size=14), text_color="#4CAF50")
        format_detail2.place(x=330, y=410)

        format_detail3 = ctk.CTkLabel(self, text="và", font=ctk.CTkFont(size=14), text_color="black")
        format_detail3.place(x=370, y=410)

        format_detail4 = ctk.CTkLabel(self, text="Notepad", font=ctk.CTkFont(size=14), text_color="#ff3b30")
        format_detail4.place(x=390, y=410)

        format_detail5 = ctk.CTkLabel(self, text=")", font=ctk.CTkFont(size=14), text_color="black")
        format_detail5.place(x=450, y=410)

        bullet7 = ctk.CTkLabel(self, 
                               text="- Tốc Độ Check Số Điện Thoại ( Được cải tiến mạnh vì chúng tôi hiểu rằng đây chính là cốt lõi đã", 
                               font=ctk.CTkFont(size=14), text_color="black", wraplength=520)
        bullet7.place(x=20, y=440)

        bullet7_cont = ctk.CTkLabel(self, 
                                    text="thay đổi phương thức", 
                                    font=ctk.CTkFont(size=14), text_color="black")
        bullet7_cont.place(x=20, y=460)

        check_method = ctk.CTkLabel(self, 
                                    text="check mới nhanh hơn nhẹ hơn", 
                                    font=ctk.CTkFont(size=14), text_color="#0066cc")
        check_method.place(x=160, y=460)

        and_text2 = ctk.CTkLabel(self, 
                                 text="và", 
                                 font=ctk.CTkFont(size=14), text_color="black")
        and_text2.place(x=350, y=460)

        savings = ctk.CTkLabel(self, 
                               text="tiết kiệm thời gian cũng như tài nguyên", 
                               font=ctk.CTkFont(size=14), text_color="#0066cc")
        savings.place(x=370, y=460)

        # Footer
        footer_label1 = ctk.CTkLabel(self, 
                                     text="LỜI KẾT: ", 
                                     font=ctk.CTkFont(size=14, weight="bold"), text_color="black")
        footer_label1.place(x=20, y=490)

        footer_label2 = ctk.CTkLabel(self, 
                                     text="Học Viện Kinh Doanh Online", 
                                     font=ctk.CTkFont(size=14, weight="bold"), text_color="#0066cc")
        footer_label2.place(x=85, y=490)

        footer_message = ctk.CTkLabel(self, 
                                      text="Gửi Tới Khách Hàng Đã Luôn Tin Dùng Sản Phẩm Lời Cảm Ơn Chân Thành Nhất,", 
                                      font=ctk.CTkFont(size=12), text_color="black")
        footer_message.place(x=289, y=490)

        footer_end = ctk.CTkLabel(self,
                                  text="Xin Kính Quy khách Kinh Doanh Thuận Lợi Và Gặt Hái Nhiều Thành Công !", 
                                  font=ctk.CTkFont(size=16, weight="bold"), text_color="#0066cc")
        footer_end.place(x=20, y=520)

class LienHePage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="white")
        label_title = ctk.CTkLabel(self, text="Học viện Kinh doanh Online", font=("Arial", 25, "bold"), text_color="#0066cc")
        label_title.place(x=20, y=10)
        title1 = ctk.CTkLabel(self, text="Học Viện Kinh Doanh Online (HKDOL) là nền tảng đào tạo chuyên sâu, cung cấp kiến thức và kỹ năng", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title1.place(x=20, y=40)
        title2 = ctk.CTkLabel(self, text="thực tiễn về kinh doanh trực tuyến. Học viện hướng đến việc hỗ trợ doanh nhân, chủ cửa hàng và cá", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title2.place(x=20, y=60)
        title3 = ctk.CTkLabel(self, text="nhân muốn phát triển kinh doanh online một cách hiệu quả và bền vững.", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title3.place(x=20, y=80)
        titlea = ctk.CTkLabel(self, text="- Chương trình đào tạo của HKDOL bao gồm nhiều chủ đề quan trọng như marketing online, quảng cáo", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea.place(x=20, y=100)
        titlea1 = ctk.CTkLabel(self, text="Facebook Ads, Google Ads, SEO, xây dựng thương hiệu cá nhân, bán hàng đa kênh và tối ưu doanh thu.", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea1.place(x=20, y=120)
        titlea2 = ctk.CTkLabel(self, text="Học viên được hướng dẫn theo lộ trình bài bản, kết hợp lý thuyết và thực hành thực tế.", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea2.place(x=20, y=140)
        titlea3 = ctk.CTkLabel(self, text="- Đội ngũ giảng viên tại HKDOL là những chuyên gia giàu kinh nghiệm trong lĩnh vực thương mại điện tử", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea3.place(x=20, y=160)
        titlea4 = ctk.CTkLabel(self, text="và tiếp thị số, giúp học viên nắm bắt xu hướng mới nhất và áp dụng vào công việc kinh doanh. Ngoài ra,", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea4.place(x=20, y=180)
        titlea5 = ctk.CTkLabel(self, text="học viện còn cung cấp các buổi tư vấn, hỗ trợ cá nhân hóa để đảm bảo học viên có thể triển khai chiến", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea5.place(x=20, y=200)
        titlea6 = ctk.CTkLabel(self, text="lược kinh doanh một cách hiệu quả.", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea6.place(x=20, y=220)
        titlea7 = ctk.CTkLabel(self, text="- Với phương châm Học đi đôi với hành, HKDOL cam kết mang đến giải pháp giáo dục thực tiễn, giúp", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea7.place(x=20, y=240)
        titlea8 = ctk.CTkLabel(self, text="học viên nhanh chóng đạt được kết quả trong môi trường kinh doanh trực tuyến đầy cạnh tranh.", 
                              font=ctk.CTkFont(size=16), text_color="black")
        titlea8.place(x=20, y=260)
        title4 = ctk.CTkLabel(self, text="Thông Tin Liên Hệ:", 
                              font=ctk.CTkFont("Arial", 22, "bold"), text_color="#0066cc")
        title4.place(x=20, y=300)
        title5 = ctk.CTkLabel(self, text="Hotline: 0971325870", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title5.place(x=20, y=325)
        title6 = ctk.CTkLabel(self, text="Zalo: 0971325870", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title6.place(x=20, y=350)
        title7 = ctk.CTkLabel(self, text="Facebook: Nguyễn Văn Huynh (Huynh Guru)", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title7.place(x=20, y=375)
        title8 = ctk.CTkLabel(self, text="Group Facebook: Học Viện Kinh Doanh Online", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title8.place(x=20, y=400)
        title9 = ctk.CTkLabel(self, text="Website: https://aff.hocvienkinhdoanhonline.com", 
                              font=ctk.CTkFont(size=16), text_color="black")
        title9.place(x=20, y=425)


class CheckZaloPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="white")
        self.sdt_list = []
        self.results = []  # Mỗi phần tử là dict có keys: sdt, ten, status, proxy
        self.stop_event = threading.Event()
        self.check_thread = None

        self.treeview_x = 0
        self.treeview_y = 0
        self.treeview_width = 800
        self.treeview_height = 450

        self.total_label_x = 0
        self.total_label_y = 555

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading",
                        font=("Arial", 11),
                        background="#1E40AF",
                        foreground="white")
        style.configure("Treeview",
                        rowheight=20,
                        font=("Arial", 10))
        columns = ("stt", "sdt", "ten", "trang_thai", "proxy")
        self.table = ttk.Treeview(self, columns=columns, show="headings")
        self.table.heading("stt", text="STT")
        self.table.heading("sdt", text="SĐT")
        self.table.heading("ten", text="TÊN")
        self.table.heading("trang_thai", text="TRẠNG THÁI")
        self.table.heading("proxy", text="PROXY")
        self.table.column("stt", width=10, anchor="center")
        self.table.column("sdt", width=100, anchor="center")
        self.table.column("ten", width=100, anchor="center")
        self.table.column("trang_thai", width=90, anchor="center")
        self.table.column("proxy", width=300, anchor="center")
        self.table.place(x=self.treeview_x, y=self.treeview_y, width=self.treeview_width, height=self.treeview_height)

        self.table.bind("<Control-v>", self.on_ctrl_v)

        self.btn_start = ctk.CTkButton(self, text="▶️ Chạy", fg_color="#1E40AF", command=self.start_check, width=150, height=40)
        self.btn_start.place(x=0, y=465)

        self.btn_stop = ctk.CTkButton(self, text="⏹ Dừng", fg_color="#1E40AF", command=self.stop_check, width=150, height=40)
        self.btn_stop.place(x=160, y=465)

        self.btn_input = ctk.CTkButton(self, text="📥 Nhập File SĐT", fg_color="#1E40AF", command=self.input_sdt, width=100, height=40)
        self.btn_input.place(x=320, y=465)

        self.btn_clear = ctk.CTkButton(self, text="🗑 Clear", fg_color="#1E40AF", command=self.clear_sdt, width=100, height=40)
        self.btn_clear.place(x=440, y=465)

        self.btn_export_excel = ctk.CTkButton(self, text="📊 Xuất Excel", fg_color="#1E40AF", command=self.export_excel, width=100, height=40)
        self.btn_export_excel.place(x=550, y=465)

        self.btn_export_txt = ctk.CTkButton(self, text="📝 Xuất TXT", fg_color="#1E40AF", command=self.export_txt, width=100, height=40)
        self.btn_export_txt.place(x=660, y=465)

        self.total_frame = ctk.CTkFrame(self, fg_color="white")
        self.total_frame.place(x=self.total_label_x, y=self.total_label_y)
        self.lbl_total_all = ctk.CTkLabel(self.total_frame, text="Tổng: 0 |", font=ctk.CTkFont(size=16, weight="bold"), text_color="black")
        self.lbl_total_all.grid(row=0, column=0, padx=5)
        self.lbl_live = ctk.CTkLabel(self.total_frame, text="Có Zalo: 0 |", font=ctk.CTkFont(size=16), text_color="green")
        self.lbl_live.grid(row=0, column=1, padx=5)
        self.lbl_die = ctk.CTkLabel(self.total_frame, text="Không Xác Định: 0 |", font=ctk.CTkFont(size=16), text_color="red")
        self.lbl_die.grid(row=0, column=2, padx=5)
        self.lbl_locked = ctk.CTkLabel(self.total_frame, text="Khoá: 0 |", font=ctk.CTkFont(size=16), text_color="#B39600")
        self.lbl_locked.grid(row=0, column=3, padx=5)
        self.lbl_vhh = ctk.CTkLabel(self.total_frame, text="VHH: 0 |", font=ctk.CTkFont(size=16), text_color="blue")
        self.lbl_vhh.grid(row=0, column=4, padx=5)

    def update_total_label(self):
        total = len(self.sdt_list)
        count_live = sum(1 for r in self.results if r.get("status") == "Live")
        count_die = sum(1 for r in self.results if r.get("status") in ["Die", "Không xác định", "Captcha Lỗi"])
        count_locked = sum(1 for r in self.results if r.get("status") == "Khoá")
        count_vhh = sum(1 for r in self.results if r.get("status") == "VHH")
        self.lbl_total_all.configure(text=f"Tổng: {total}")
        self.lbl_live.configure(text=f"Có Zalo: {count_live}")
        self.lbl_die.configure(text=f"Không Xác Định: {count_die}")
        self.lbl_locked.configure(text=f"Khoá: {count_locked}")
        self.lbl_vhh.configure(text=f"VHH: {count_vhh}")

    def input_sdt(self):
        file_path = filedialog.askopenfilename(title="Chọn file SĐT", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    numbers = [line.strip() for line in f if line.strip()]
                self.sdt_list = numbers
                self.results = []
                for item in self.table.get_children():
                    self.table.delete(item)
                self.update_total_label()
                messagebox.showinfo("Thông báo", f"Đã thêm {len(numbers)} số điện thoại")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")

    def clear_sdt(self):
        self.sdt_list = []
        self.results = []
        for item in self.table.get_children():
            self.table.delete(item)
        self.update_total_label()

    def start_check(self):
        if self.check_thread and self.check_thread.is_alive():
            messagebox.showwarning("Chú ý", "Quá trình kiểm tra đang chạy")
            return
        if not self.sdt_list:
            messagebox.showwarning("Chú ý", "Chưa có số điện thoại nào được nhập")
            return
        self.stop_event.clear()
        self.check_thread = threading.Thread(target=self.check_task)
        self.check_thread.start()

    def stop_check(self):
        self.stop_event.set()

    def check_task(self):
        for idx, sdt in enumerate(self.sdt_list, start=1):
            if self.stop_event.is_set():
                break
            result = check_zalo_account(sdt)
            self.results.append({"sdt": sdt,
                                 "ten": result.get("ten", ""),
                                 "status": result.get("status", ""),
                                 "proxy": result.get("proxy", "KHÔNG DÙNG PROXY")})
            self.table.insert("", "end", values=(idx, sdt, result.get("ten", ""), result.get("status", ""), result.get("proxy", "KHÔNG DÙNG PROXY")))
            self.update_total_label()
            self.table.yview_moveto(1)

    def export_excel(self):
        live_results = [r for r in self.results if r.get("status") == "Live"]
        if not live_results:
            messagebox.showwarning("Chú ý", "Không có số điện thoại live nào")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=(("Excel files", "*.xlsx"),))
        if file_path:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Live SDT"
            ws.append(["SĐT", "NAME"])
            for r in live_results:
                ws.append([r.get("sdt"), r.get("ten")])
            try:
                wb.save(file_path)
                messagebox.showinfo("Thành công", f"Xuất Excel thành công: {file_path}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi khi lưu file: {e}")

    def export_txt(self):
        live_results = [r for r in self.results if r.get("status") == "Live"]
        if not live_results:
            messagebox.showwarning("Chú ý", "Không có số điện thoại live nào")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=(("Text files", "*.txt"),))
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    for r in live_results:
                        f.write(r.get("sdt") + "\n")
                messagebox.showinfo("Thành công", f"Xuất TXT thành công: {file_path}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi khi lưu file: {e}")

    def on_ctrl_v(self, event):
        try:
            clip = self.clipboard_get()
        except Exception:
            return
        numbers = [x.strip() for x in clip.splitlines() if x.strip()]
        if not numbers:
            return
        ans = messagebox.askokcancel("Xác nhận", f"Bạn có chắc chắn muốn dán {len(numbers)} số điện thoại?")
        if ans:
            self.sdt_list.extend(numbers)
            self.update_total_label()
            messagebox.showinfo("Thông báo", f"Đã thêm {len(numbers)} số điện thoại từ clipboard")
class TaiKhoanPage(ctk.CTkFrame):
    def __init__(self, parent, login_data):
        super().__init__(parent, fg_color="white")
        self.login_data = login_data
        # Tạo layout dạng grid
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        # ----- DÒNG 1: Họ và Tên -----
        label_name = ctk.CTkLabel(self, text="Họ & Tên:", font=("Arial", 14, "bold"), text_color="#333")
        label_name.grid(row=0, column=0, padx=10, pady=10, sticky="e")

        val_name = ctk.CTkLabel(self, text=self.login_data.get("name", ""), font=("Arial", 14))
        val_name.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # ----- DÒNG 2: IP MAC (hoặc địa chỉ MAC) -----
        label_mac = ctk.CTkLabel(self, text="IP MAC:", font=("Arial", 14, "bold"), text_color="#333")
        label_mac.grid(row=1, column=0, padx=10, pady=10, sticky="e")

        val_mac = ctk.CTkLabel(self, text=self.login_data.get("mac", ""), font=("Arial", 14))
        val_mac.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        # ----- DÒNG 3: API KEY -----
        label_key = ctk.CTkLabel(self, text="API KEY:", font=("Arial", 14, "bold"), text_color="#333")
        label_key.grid(row=2, column=0, padx=10, pady=10, sticky="e")

        val_key = ctk.CTkLabel(self, text=self.login_data.get("key", ""), font=("Arial", 14))
        val_key.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        # ----- DÒNG 4: QUYỀN HẠN -----
        label_role = ctk.CTkLabel(self, text="QUYỀN HẠN:", font=("Arial", 14, "bold"), text_color="#333")
        label_role.grid(row=3, column=0, padx=10, pady=10, sticky="e")

        val_role = ctk.CTkLabel(self, text=self.login_data.get("Role", ""), font=("Arial", 14))
        val_role.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        # ----- DÒNG 5: Thời Gian -----
        label_time = ctk.CTkLabel(self, text="Thời Gian:", font=("Arial", 14, "bold"), text_color="#333")
        label_time.grid(row=4, column=0, padx=10, pady=10, sticky="e")

        val_time = ctk.CTkLabel(self, text=self.login_data.get("time", ""), font=("Arial", 14))
        val_time.grid(row=4, column=1, padx=10, pady=10, sticky="w")

        # ----- DÒNG 6: Kích Hoạt -----
        label_active = ctk.CTkLabel(self, text="Kích Hoạt:", font=("Arial", 14, "bold"), text_color="#333")
        label_active.grid(row=5, column=0, padx=10, pady=10, sticky="e")

        # Đổi text tuỳ theo giá trị "active"
        if self.login_data.get("Active", "no").lower() == "yes":
            active_text = "Đã Kích Hoạt"
            active_color = "green"
        else:
            active_text = "Chưa Kích Hoạt"
            active_color = "red"

        val_active = ctk.CTkLabel(self, text=active_text, font=("Arial", 14, "bold"), text_color=active_color)
        val_active.grid(row=5, column=1, padx=10, pady=10, sticky="w")

        # ----- NÚT ĐĂNG XUẤT -----
        logout_button = ctk.CTkButton(
            self, 
            text="ĐĂNG XUẤT", 
            width=200, 
            height=40, 
            fg_color="#FF3333",
            command=self.logout
        )
        logout_button.place(x=220, y=325)

    def logout(self):
        """Đóng toàn bộ ứng dụng (hoặc quay lại trang đăng nhập tuỳ ý)."""
        result = messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn đăng xuất?")
        if result:
            self._root().destroy()  # Đóng cửa sổ chính
            # Hoặc bạn có thể mở lại cửa sổ login, tuỳ logic bạn muốn


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="white")
        self.cookie_file_path = ""
        self.proxy_file_path = ""
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.cookie_file_path = config.get("cookie_file", "")
                    self.proxy_file_path = config.get("proxy_file", "")
                    use_proxy_flag = config.get("use_proxy", False)
            except:
                use_proxy_flag = False
        else:
            use_proxy_flag = False

        self.btn_input_cookie = ctk.CTkButton(self, text="📥 Nhập File Cookie", fg_color="#1E40AF", command=self.input_cookie, width=150, height=40)
        self.btn_input_cookie.place(x=20, y=20)
        self.lbl_cookie_path = ctk.CTkLabel(self, text=self.cookie_file_path if self.cookie_file_path else "No file selected", font=ctk.CTkFont(size=14))
        self.lbl_cookie_path.place(x=180, y=23)

        self.btn_input_proxy = ctk.CTkButton(self, text="📥 Nhập File Proxy", fg_color="#1E40AF", command=self.input_proxy, width=150, height=40)
        self.btn_input_proxy.place(x=20, y=70)
        self.lbl_proxy_path = ctk.CTkLabel(self, text=self.proxy_file_path if self.proxy_file_path else "No file selected", font=ctk.CTkFont(size=14))
        self.lbl_proxy_path.place(x=180, y=73)

        self.chk_use_proxy = ctk.CTkCheckBox(self, text="Có sử dụng proxy không?")
        self.chk_use_proxy.place(x=20, y=120)
        self.luuy = ctk.CTkLabel(self, text="( Lưu ý: Sử dụng proxy sẽ giúp check số điện thoại ổn định hơn )", font=ctk.CTkFont(size=14), text_color="red")
        self.luuy.place(x=210, y=120)
        if use_proxy_flag:
            self.chk_use_proxy.select()
        else:
            self.chk_use_proxy.deselect()

        self.btn_save = ctk.CTkButton(self, text="Save", fg_color="#1E40AF", command=self.save_settings)
        self.btn_save.place(x=20, y=170)

    def input_cookie_file():
    file_path = filedialog.askopenfilename(title="Chọn file cookie (.txt)", filetypes=[("Text files", "*.txt")])
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) < 2:
            messagebox.showerror("Lỗi", "File không đủ dữ liệu (cần 2 dòng)")
        else:
            global ORIGINAL_COOKIE, ORIGINAM_TOKEN
            ORIGINAL_COOKIE = lines[0].strip()
            ORIGINAM_TOKEN = lines[1].strip()
            messagebox.showinfo("Thành công", "Cookie và Token đã được cập nhật")


    def input_proxy(self):
        file_path = filedialog.askopenfilename(title="Chọn file proxy", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        if file_path:
            self.proxy_file_path = file_path
            self.lbl_proxy_path.configure(text=file_path)

    def save_settings(self):
        use_proxy_flag = self.chk_use_proxy.get()
        if use_proxy_flag:
            if self.proxy_file_path:
                try:
                    with open(self.proxy_file_path, "r", encoding="utf-8") as f:
                        proxy_lines = [line.strip() for line in f if line.strip()]
                    global PROXIES, USE_PROXY, PROXY_INDEX
                    PROXIES = proxy_lines
                    USE_PROXY = True
                    PROXY_INDEX = 0
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Lỗi khi đọc file proxy: {e}")
                    return
            else:
                messagebox.showerror("Lỗi", "Chưa chọn file proxy")
                return
        else:
            USE_PROXY = False

        config = {
            "cookie_file": self.cookie_file_path,
            "proxy_file": self.proxy_file_path,
            "use_proxy": use_proxy_flag
        }
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("Thành công", "Cài đặt đã được lưu")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi lưu cài đặt: {e}")

HEADERS_INFO = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "vi-VN,vi;q=0.9",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

def get_zalo_info(sdt, captcha_uuid=None, proxy=None):
    url = f"https://zalo.me/{sdt}"
    cookie = ORIGINAL_COOKIE
    if captcha_uuid:
        cookie += f" z-captcha-response={captcha_uuid}"
    headers = HEADERS_INFO.copy()
    headers["Cookie"] = cookie
    try:
        if proxy:
            response = requests.get(url, headers=headers, proxies=proxy, timeout=10)
        else:
            response = requests.get(url, headers=headers, timeout=10)
    except Exception:
        return {"captcha_required": False, "html": ""}
    html = response.text
    if "Để tránh việc spam hay thu thập thông tin trái phép" in html:
        return {"captcha_required": True, "html": html}
    else:
        return {"captcha_required": False, "html": html}

def get_captcha(proxy=None):
    url = "https://zcaptcha.api.zaloapp.com/api/get-captcha"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Cookie": ORIGINAL_COOKIE,
        "Accept-Language": "vi-VN,vi;q=0.9",
        "csrf-token": ORIGINAM_TOKEN
    }
    data = {}
    try:
        if proxy:
            resp = requests.post(url, headers=headers, json=data, proxies=proxy, timeout=10)
        else:
            resp = requests.post(url, headers=headers, json=data, timeout=10)
    except Exception:
        return None
    if resp.status_code == 200:
        result = resp.json()
        if result.get("error_code") == 0:
            data = result.get("data", {})
            image_data = data.get("image", {})
            return {
                "url": image_data.get("url"),
                "token": image_data.get("token"),
                "question": data.get("question")
            }
    return None

def solve_captcha(image_url, question, proxy=None):
    try:
        if proxy:
            image_resp = requests.get(image_url, proxies=proxy, timeout=10)
        else:
            image_resp = requests.get(image_url, timeout=10)
    except Exception:
        return None
    if image_resp.status_code != 200:
        return None
    base64_image = base64.b64encode(image_resp.content).decode("utf-8")
    API_KEY = "AIzaSyCfnPZg0yVDm9YHP2SoeRNxRJACvuwuXtE"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    text_prompt = (f"Tôi cần bạn trả lời bằng tiếng việt: {question}, trong ảnh sẽ có tổng 9 bức ảnh và bức ảnh bạn chọn lần lượt là số mấy, "
                   "tôi cần bạn trả lời mặc định chỉ hiển thị mỗi số thứ tự bức ảnh mà bạn chọn")
    data = {
        "contents": [
            {
                "parts": [
                    {"text": text_prompt},
                    {"inline_data": {"mime_type": "image/png", "data": base64_image}}
                ]
            }
        ]
    }
    try:
        if proxy:
            resp = requests.post(url, headers=headers, json=data, proxies=proxy, timeout=10)
        else:
            resp = requests.post(url, headers=headers, json=data, timeout=10)
    except Exception:
        return None
    if resp.status_code == 200:
        try:
            answer = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return answer.strip()
        except (KeyError, IndexError):
            return None
    return None

def check_captcha(token, answer_str, proxy=None):
    try:
        selected = [int(x) for x in answer_str.replace(" ", "").split(",")]
    except Exception:
        return None
    answers = [(True if pos in selected else False) for pos in range(1, 10)]
    url = "https://zcaptcha.api.zaloapp.com/api/check-captcha"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "vi-VN,vi;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Cookie": ORIGINAL_COOKIE,
        "csrf-token": ORIGINAM_TOKEN,
        "Host": "zcaptcha.api.zaloapp.com",
        "Origin": "https://zcaptcha.api.zaloapp.com",
        "Referer": "https://zcaptcha.api.zaloapp.com/zcaptcha-challenge?appId=3032357805345395173&lang=vi",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Storage-Access": "active",
        "User-Agent": HEADERS_INFO["User-Agent"]
    }
    payload = {"answers": answers, "token": token}
    try:
        if proxy:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), proxies=proxy, timeout=10)
        else:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
    except Exception:
        return None
    if resp.status_code == 200:
        result = resp.json()
        if result.get("error_code") == 0 and result.get("data", {}).get("pass") is True:
            uuid_value = result["data"].get("uuid")
            with open("uuid.txt", "w", encoding="utf-8") as f:
                f.write(uuid_value)
            return uuid_value
    return None

def check_zalo_account(sdt):
    # Nếu sử dụng proxy, lấy proxy mới cho mỗi request
    proxy_used = get_next_proxy() if USE_PROXY else None
    info = get_zalo_info(sdt, proxy=proxy_used)
    if not info["captcha_required"]:
        html = info["html"]
        if '<meta property="og:title" content="Zalo - Tài khoản bị khóa" />' in html:
            return {"status": "Khoá", "ten": "", "proxy": proxy_used["http"] if proxy_used else "KHÔNG DÙNG PROXY"}
        elif '<figcaption>Tài khoản này tạm thời không thể sử dụng chức năng này</figcaption>' in html:
            return {"status": "VHH", "ten": "", "proxy": proxy_used["http"] if proxy_used else "KHÔNG DÙNG PROXY"}
        elif '<figcaption>Tài khoản này không tồn tại hoặc không cho phép tìm kiếm</figcaption>' in html:
            return {"status": "Die", "ten": "", "proxy": proxy_used["http"] if proxy_used else "KHÔNG DÙNG PROXY"}
        else:
            match = re.search(r'<meta property="og:title" content="Zalo - (.+?)" />', html)
            if match:
                ten = match.group(1)
                return {"status": "Live", "ten": ten, "proxy": proxy_used["http"] if proxy_used else "KHÔNG DÙNG PROXY"}
            else:
                return {"status": "Không xác định", "ten": "", "proxy": proxy_used["http"] if proxy_used else "KHÔNG DÙNG PROXY"}
    else:
        # Nếu captcha yêu cầu, sử dụng proxy riêng cho từng bước
        proxy_captcha = get_next_proxy() if USE_PROXY else None
        cap_data = get_captcha(proxy=proxy_captcha)
        if not cap_data:
            return {"status": "Captcha Lỗi", "ten": "", "proxy": proxy_captcha["http"] if proxy_captcha else "KHÔNG DÙNG PROXY"}
        image_url = cap_data["url"]
        question = cap_data["question"]
        token = cap_data["token"]
        proxy_solve = get_next_proxy() if USE_PROXY else None
        answer_str = solve_captcha(image_url, question, proxy=proxy_solve)
        if not answer_str:
            return {"status": "Captcha Lỗi", "ten": "", "proxy": proxy_solve["http"] if proxy_solve else "KHÔNG DÙNG PROXY"}
        proxy_check = get_next_proxy() if USE_PROXY else None
        uuid_value = check_captcha(token, answer_str, proxy=proxy_check)
        if not uuid_value:
            return {"status": "Captcha Lỗi", "ten": "", "proxy": proxy_check["http"] if proxy_check else "KHÔNG DÙNG PROXY"}
        # Sau captcha, lấy proxy mới cho lần request cuối
        proxy_final = get_next_proxy() if USE_PROXY else None
        info = get_zalo_info(sdt, captcha_uuid=uuid_value, proxy=proxy_final)
        html = info["html"]
        if '<meta property="og:title" content="Zalo - Tài khoản bị khóa" />' in html:
            return {"status": "Khoá", "ten": "", "proxy": proxy_final["http"] if proxy_final else "KHÔNG DÙNG PROXY"}
        elif '<figcaption>Tài khoản này tạm thời không thể sử dụng chức năng này</figcaption>' in html:
            return {"status": "VHH", "ten": "", "proxy": proxy_final["http"] if proxy_final else "KHÔNG DÙNG PROXY"}
        elif '<figcaption>Tài khoản này không tồn tại hoặc không cho phép tìm kiếm</figcaption>' in html:
            return {"status": "Die", "ten": "", "proxy": proxy_final["http"] if proxy_final else "KHÔNG DÙNG PROXY"}
        else:
            match = re.search(r'<meta property="og:title" content="Zalo - (.+?)" />', html)
            if match:
                ten = match.group(1)
                return {"status": "Live", "ten": ten, "proxy": proxy_final["http"] if proxy_final else "KHÔNG DÙNG PROXY"}
            else:
                return {"status": "Không xác định", "ten": "", "proxy": proxy_final["http"] if proxy_final else "KHÔNG DÙNG PROXY"}




def read_sdt_from_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

# ---------------------------
# CHẠY CHƯƠNG TRÌNH
# ---------------------------
# TẠO CỬA SỔ LOGIN
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
login_window = ctk.CTk()  
login_window.title("Zalo Checker v2.0 | Đăng Nhập")
login_window.geometry("700x500")
login_window.resizable(False, False)
if os.path.exists("logo.ico"):
    login_window.iconbitmap("logo.ico")

# Khung bên trái (form đăng nhập)
left_frame = ctk.CTkFrame(master=login_window, width=300, corner_radius=0)
left_frame.pack(side="left", fill="both", expand=False)
left_frame.configure(fg_color="white")

if os.path.exists("logo.png"):
    logo_image = ctk.CTkImage(
        dark_image=Image.open("logo.png"),
        size=(90, 70)
    )
    logo_label = ctk.CTkLabel(left_frame, image=logo_image, text="")
    logo_label.place(x=15, y=90)

title_label = ctk.CTkLabel(
    left_frame,
    text="Đăng Nhập !",
    font=("Arial", 24, "bold"),
    text_color="#333"
)
title_label.place(x=20, y=170)

subtitle_label = ctk.CTkLabel(
    left_frame,
    text="Học Viện Kinh Doanh Online Hân Hạnh Phục Vụ Bạn",
    font=("Arial", 11, "italic"),
    text_color="#666"
)
subtitle_label.place(x=20, y=198)

saved_key = load_key_from_file()
key_entry = ctk.CTkEntry(
    left_frame,
    placeholder_text="Nhập key của bạn",
    width=240,
    height=35,
    corner_radius=8
)
key_entry.place(x=20, y=240)
key_entry.insert(0, saved_key)

mac_label = ctk.CTkLabel(left_frame, text="Địa Chỉ MAC:", font=("Arial", 12), text_color="#333")
mac_label.place(x=20, y=280)

mac_address = get_mac_address()
mac_display = ctk.CTkLabel(
    left_frame,
    text=mac_address,
    font=("Arial", 12, "bold"),
    text_color="Green",
    cursor="hand2"
)
mac_display.place(x=100, y=280)
mac_display.bind("<Button-1>", lambda e: copy_to_clipboard(mac_address, login_window))

save_key_var = ctk.BooleanVar(value=bool(saved_key))
save_key_chk = ctk.CTkCheckBox(
    master=left_frame,
    text="Lưu key cho lần sau",
    variable=save_key_var,
    text_color="#333"
)
save_key_chk.place(x=20, y=320)

login_button = ctk.CTkButton(
    master=left_frame,
    text="ĐĂNG NHẬP",
    width=240,
    height=40,
    corner_radius=8,
    fg_color="#0072FF",
    text_color="white",
    font=("Arial", 14, "bold"),
    command=lambda: check_key(login_window)  # Truyền tham chiếu cửa sổ
)
login_button.place(x=20, y=360)

# Khung bên phải (ảnh banner)
right_frame = ctk.CTkFrame(master=login_window, corner_radius=0)
right_frame.pack(side="right", fill="both", expand=True)
right_frame.configure(fg_color="white")

if os.path.exists("banner.png"):
    bg_image = ctk.CTkImage(
        dark_image=Image.open("banner.png"),
        size=(380, 480)
    )
    bg_label = ctk.CTkLabel(right_frame, image=bg_image, text="")
    bg_label.place(x=0, y=0)
else:
    bg_label = ctk.CTkLabel(
        right_frame,
        text="Zalo Checker v2.0\nHọc Viện Kinh Doanh Online",
        font=("Arial", 24, "bold"),
        text_color="#004F9F"
    )
    bg_label.place(x=100, y=50)

login_window.mainloop()
