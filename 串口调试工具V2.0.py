import customtkinter as ctk
import serial.tools.list_ports
import serial
import threading
import time
import re
import tkinter as tk  # 必须导入tkinter获取END常量

class SerialTool(ctk.CTk):
    # 可用串口列表（设备名）
    available_ports = ['None']
    # 可用串口描述列表
    available_ports_descriptions = ['None']
    # 波特率列表
    baud_rates = ['9600', '19200', '38400', '57600', '115200']
    # 数据位列表
    data_bits = ['5', '6', '7', '8']
    # 停止位列表
    stop_bits = ['1', '2']
    # 校验位列表
    parity_bits = ['None', 'Odd', 'Even']

    # 调试关键词颜色值表
    debug_color_dict = {
        "default" : "black",
        "info"    : "#38b338",
        "error"   : "#ff0000",
        "warning" : "#ff9900",
        "debug"   : "#ff9fae",
        "send"    : "#0099ff",
        "system"  : "#ae00ff"
    }

    # 接收数据框底部跟踪是否开启
    is_receive_bottom_track = True

    def __init__(self, fg_color=None, **kwargs):
        super().__init__(fg_color, **kwargs)
        
        # 初始化变量
        self.auto_newline_var = ctk.BooleanVar(value=True)
        self.timer_send_var = ctk.BooleanVar(value=False)  # 定时发送开关
        self.auto_scan_var = ctk.BooleanVar(value=True)    # 修复：保存自动扫描开关变量
        self.debug_mode_var = ctk.BooleanVar(value=True)
        self.serial_port = None  # 串口对象
        self.is_serial_open = False  # 串口是否打开
        self.receive_thread = None  # 接收线程
        self.timer_thread = None  # 定时发送线程
        self.timer_running = False  # 定时发送是否运行
        
        # 自动扫描串口相关变量
        self.auto_scan_running = True  # 自动扫描开关
        self.auto_scan_thread = None  # 自动扫描线程
        self.last_ports = []  # 上一次扫描的串口列表（设备名），用于对比更新
        self.current_selected_port = ''  # 记录当前选中的串口（设备名）
        self.port_display_map = {}  # 显示文本 -> 真实设备名的映射
        self.system_tag = "系统提示："  # 系统提示统一标签
        
        # 界面设置
        self.title('串口调试工具')
        self.geometry('900x600')
        ctk.set_appearance_mode('light')
        #ctk.set_default_font("SimHei", 10)  # 修复：设置中文字体，解决乱码
        self.iconbitmap("icon.ico")
        # 创建界面组件
        self._create_widgets()
        
        # 初始化串口列表并启动自动扫描线程
        self._update_serial_ports()
        self._start_auto_scan()
        
        # 设置默认值
        self.baud_rate_combo.set('115200')
        self.serial_data_bits_combo.set('8')
        self.serial_stop_bits_combo.set('1')
        self.serial_parity_combo.set('None')
        self.serial_send_timer_send_newline.configure(variable=self.timer_send_var)

    def _create_widgets(self):
        # 1. 串口配置 + 串口数据输出 框架
        self.serial_cfg_output_frame = ctk.CTkFrame(self)
        self.serial_cfg_output_frame.pack(fill="both", expand=True, side="top")
        
        # 2.1 串口配置框架
        self.serial_cfg_frame = ctk.CTkFrame(self.serial_cfg_output_frame)
        self.serial_cfg_frame.pack(expand=False, side="left", anchor="nw", padx=(5, 5))
        
        # 串口选择
        self.serial_list_label = ctk.CTkLabel(self.serial_cfg_frame, text='可用串口')
        self.serial_list_label.grid(row=0, column=0, padx=(5, 5), pady=(5, 5))
        self.serial_list_combo = ctk.CTkComboBox(self.serial_cfg_frame, values=self._get_display_ports())
        self.serial_list_combo.grid(row=0, column=1, padx=(5, 5), pady=(5, 5))
        # 绑定选中事件，记录当前选中的串口（设备名）
        self.serial_list_combo.configure(command=self._on_port_selected)
        
        # 波特率
        self.baud_rate_label = ctk.CTkLabel(self.serial_cfg_frame, text='波特率')
        self.baud_rate_label.grid(row=1, column=0, padx=(5, 5), pady=(5, 5))
        self.baud_rate_combo = ctk.CTkComboBox(self.serial_cfg_frame, values=self.baud_rates)
        self.baud_rate_combo.grid(row=1, column=1, padx=(5, 5), pady=(5, 5))
        
        # 数据位
        self.serial_data_bits_label = ctk.CTkLabel(self.serial_cfg_frame, text="数据位")
        self.serial_data_bits_label.grid(row=2, column=0, padx=(5, 5), pady=(5, 5))
        self.serial_data_bits_combo = ctk.CTkComboBox(self.serial_cfg_frame, values=self.data_bits)
        self.serial_data_bits_combo.grid(row=2, column=1, padx=(5, 5), pady=(5, 5))
        
        # 停止位
        self.serial_stop_bits_label = ctk.CTkLabel(self.serial_cfg_frame, text="停止位")
        self.serial_stop_bits_label.grid(row=3, column=0, padx=(5, 5), pady=(5, 5))
        self.serial_stop_bits_combo = ctk.CTkComboBox(self.serial_cfg_frame, values=self.stop_bits)
        self.serial_stop_bits_combo.grid(row=3, column=1, padx=(5, 5), pady=(5, 5))
        
        # 校验位
        self.serial_parity_label = ctk.CTkLabel(self.serial_cfg_frame, text="校验位")
        self.serial_parity_label.grid(row=4, column=0, padx=(5, 5), pady=(5, 5))
        self.serial_parity_combo = ctk.CTkComboBox(self.serial_cfg_frame, values=self.parity_bits)
        self.serial_parity_combo.grid(row=4, column=1, padx=(5, 5), pady=(5, 5))
        
        # 打开串口按钮
        self.open_serial_btn = ctk.CTkButton(self.serial_cfg_frame, text='打开串口', 
                                            command=self._open_serial, fg_color="#2ecc71", 
                                            hover_color="#27ae60")
        self.open_serial_btn.grid(row=5, column=0, padx=(5, 5), pady=(5, 5))
        
        # 清除接收按钮
        self.clear_receive_btn = ctk.CTkButton(self.serial_cfg_frame, text="清除接收",
                                              fg_color="#3498db", hover_color="#2980b9",
                                              command=self._clear_receive)
        self.clear_receive_btn.grid(row=5, column=1, padx=(5, 5), pady=(5, 5))
        
        # 关闭串口按钮
        self.close_serial_btn = ctk.CTkButton(self.serial_cfg_frame, text="关闭串口",
                                             fg_color="#e74c3c", hover_color="#c0392b",
                                             command=self._close_serial)
        self.close_serial_btn.grid(row=6, column=0, columnspan=2, sticky="ew", padx=(5, 5), pady=(5, 5))

        # 2.2 串口数据信息输出框架
        self.serial_data_output_frame = ctk.CTkFrame(self.serial_cfg_output_frame)
        self.serial_data_output_frame.pack(fill="both", expand=True, side="right", padx=1, pady=1)
        
        # 创建CTkTextbox并保存其原生Text对象
        self.serial_info_show_entry = ctk.CTkTextbox(self.serial_data_output_frame,font=("微软雅黑", 20))
        self.serial_info_show_entry.pack(fill="both", expand=True, side="right", padx=(1, 1), pady=(1, 1))
        self.serial_info_show_entry.configure(state="normal")
        # 获取CTkTextbox内部的原生tkinter.Text对象（关键修复）
        self.text_widget = self.serial_info_show_entry._textbox
        # 鼠标右击 接收框 事件绑定
        self.serial_info_show_entry.bind("<Button-3>", self.right_click_event)
        self.serial_info_show_entry.bind("<Control-MouseWheel>", self.ctrl_scroll_increase_font)

        # 3. 串口发送数据框架
        self.serial_send_frame = ctk.CTkFrame(self)
        self.serial_send_frame.pack(fill="x", expand=False, padx=(1, 1), pady=(1, 1))
        
        # 3.1 串口发送数据输入框 + 发送按钮 + 清除接收按钮 框架
        self.serial_send_data_frame = ctk.CTkFrame(self.serial_send_frame)
        self.serial_send_data_frame.pack(fill="x", expand=True, side="top", padx=(1, 1), pady=(1, 1))
        
        # 3.1.1 串口发送输入框
        self.serial_send_data_text = ctk.CTkTextbox(self.serial_send_data_frame, height=100)
        self.serial_send_data_text.pack(fill="x", side="left", expand=True)
        
        # 3.1.3 串口发送数据按钮 + 清除发送按钮
        self.serial_send_data_btn_frame = ctk.CTkFrame(self.serial_send_data_frame)
        self.serial_send_data_btn_frame.pack(side="right", padx=(1, 1), pady=(1, 1), fill="y", anchor="c")
        
        self.serial_send_data_btn = ctk.CTkButton(self.serial_send_data_btn_frame, text="发送数据",
                                                 command=self._send_data, fg_color="#9b59b6",
                                                 hover_color="#8e44ad")
        self.serial_send_data_btn.pack(side="top", pady=(5, 5))
        
        self.serial_send_data_clear_btn = ctk.CTkButton(self.serial_send_data_btn_frame, text="清除发送",
                                                       fg_color="#f39c12", hover_color="#e67e22",
                                                       command=self._clear_send)
        self.serial_send_data_clear_btn.pack(side="top", pady=(5, 5))

        # 4. 串口发送数据配置 框架
        self.serial_send_config_frame = ctk.CTkFrame(self)
        self.serial_send_config_frame.pack(fill="x", expand=False, ipady=5, ipadx=5)
        
        # 4.1 结尾自动发送换行符 复选框
        self.serial_send_auto_send_newline = ctk.CTkCheckBox(self.serial_send_config_frame,
                                                             text="结尾自动发送换行符",
                                                             variable=self.auto_newline_var)
        self.serial_send_auto_send_newline.pack(side="left", padx=(5, 15))
        
        # 4.2 定时发送
        self.serial_send_timer_send_newline = ctk.CTkCheckBox(self.serial_send_config_frame,
                                                             text="定时发送",
                                                             variable=self.timer_send_var,  # 修复：绑定变量
                                                             command=self._toggle_timer_send)
        self.serial_send_timer_send_newline.pack(side="left", padx=(5, 5))
        
        self.serial_timer_send_label = ctk.CTkLabel(self.serial_send_config_frame, text="周期")
        self.serial_timer_send_label.pack(side="left", padx=(5, 10))
        
        self.timer_value = ctk.StringVar(value="1000")
        self.serial_timer_send_entry = ctk.CTkEntry(self.serial_send_config_frame,
                                                    textvariable=self.timer_value,
                                                    width=80)
        self.serial_timer_send_entry.pack(side="left")
        
        self.serial_timer_send_label_ms = ctk.CTkLabel(self.serial_send_config_frame, text="ms")
        self.serial_timer_send_label_ms.pack(side="left", padx=(5, 0))
        
        # 自动扫描开关（修复：绑定保存的变量）
        self.auto_scan_switch = ctk.CTkSwitch(self.serial_send_config_frame, text="自动扫描",
                                             variable=self.auto_scan_var,
                                             command=self._toggle_auto_scan)
        self.auto_scan_switch.pack(side="left", padx=(5, 0))

        # 调试模式开关
        self.debug_mode_switch = ctk.CTkSwitch(self.serial_send_config_frame, text="调试模式",
                                               variable = self.debug_mode_var,
                                               )
        self.debug_mode_switch.pack(side="left", padx=(5, 0))

        # ========== 关键修改：系统提示Label ==========
        self.system_tip_label = ctk.CTkLabel(
            self.serial_send_config_frame,
            text="系统提示",
            text_color = "purple",
        )
        self.system_tip_label.pack(side="right", padx=(5, 5))

    def _configure_text_tags(self):
        """配置文本框的颜色标签（对原生Text对象操作）"""
        for tag in self.debug_color_dict:
            self.text_widget.tag_configure(tag, foreground = self.debug_color_dict[tag])


    def _get_display_ports(self):
        """生成显示用的串口列表"""
        display_ports = []
        self.port_display_map.clear()
        
        if len(self.available_ports) == 0:
            display_ports = ['None']
            self.port_display_map['None'] = 'None'
        else:
            for i, port in enumerate(self.available_ports):
                desc = self.available_ports_descriptions[i] if i < len(self.available_ports_descriptions) else '未知设备'
                if not desc or desc.strip() == '' or 'n/a' in desc.lower():
                    desc = '未知设备'
                display_text = f"{port} - {desc}"
                display_ports.append(display_text)
                self.port_display_map[display_text] = port
        
        return display_ports

    def _on_port_selected(self, selected_display_text):
        """记录选中的串口"""
        self.current_selected_port = self.port_display_map.get(selected_display_text, 'None')

    def _start_auto_scan(self):
        """启动自动扫描线程"""
        self.auto_scan_running = True
        self.auto_scan_thread = threading.Thread(target=self._auto_scan_ports, daemon=True)
        self.auto_scan_thread.start()

    def _auto_scan_ports(self):
        """自动扫描串口"""
        while self.auto_scan_running:
            try:
                ports = serial.tools.list_ports.comports()
                current_ports = []
                current_descriptions = []
                
                if ports:
                    for port in ports:
                        current_ports.append(port.device)
                        desc = f"{port.name} ({port.description})" if port.description else port.name
                        current_descriptions.append(desc)
                else:
                    current_ports = ['None']
                    current_descriptions = ['无可用串口']
                
                if current_ports != self.last_ports:
                    self.last_ports = current_ports.copy()
                    self.available_ports = current_ports
                    self.available_ports_descriptions = current_descriptions
                    display_ports = self._get_display_ports()
                    self.after(0, lambda: self._update_port_combobox(display_ports))
                
                time.sleep(0.5)
                
            except Exception as e:
                error_msg = f"串口自动扫描出错: {str(e)}\n"
                self.after(0, self._append_receive_text, error_msg, "error")
                time.sleep(0.5)

    def _update_port_combobox(self, display_ports):
        """更新串口下拉框"""
        try:
            current_display_selection = self.serial_list_combo.get()
            self.serial_list_combo.configure(values=display_ports)
            
            if self.current_selected_port:
                selected_display_text = None
                for display_text, port in self.port_display_map.items():
                    if port == self.current_selected_port:
                        selected_display_text = display_text
                        break
                if selected_display_text and selected_display_text in display_ports:
                    self.serial_list_combo.set(selected_display_text)
            elif current_display_selection in display_ports:
                self.serial_list_combo.set(current_display_selection)
            elif display_ports:
                self.serial_list_combo.set(display_ports[0])
            
        except Exception as e:
            self._append_receive_text(f"更新串口列表UI出错: {str(e)}\n", "error")

    def _toggle_auto_scan(self):
        """切换自动扫描"""
        if self.auto_scan_var.get():
            if not self.auto_scan_running:
                self._start_auto_scan()
                self._append_receive_text(f"{self.system_tag}串口自动扫描已开启（500ms/次）\n", "system")
        else:
            self.auto_scan_running = False
            if self.auto_scan_thread and self.auto_scan_thread.is_alive():
                self.auto_scan_thread.join(timeout=1)
            self._append_receive_text(f"{self.system_tag}串口自动扫描已关闭\n", "system")


    def _update_serial_ports(self):
        """初始化串口列表"""
        try:
            ports = serial.tools.list_ports.comports()
            self.available_ports = []
            self.available_ports_descriptions = []
            
            if ports:
                for port in ports:
                    self.available_ports.append(port.device)
                    desc = f"{port.name} ({port.description})" if port.description else port.name
                    self.available_ports_descriptions.append(desc)
            else:
                self.available_ports = ['None']
                self.available_ports_descriptions = ['无可用串口']
            
            self.last_ports = self.available_ports.copy()
            display_ports = self._get_display_ports()
            self._update_port_combobox(display_ports)
            
        except Exception as e:
            self._append_receive_text(f"{self.system_tag}初始化串口列表失败: {str(e)}\n", "error")
            self.available_ports = ['None']
            self.available_ports_descriptions = ['无可用串口']
            self.last_ports = ['None']

    # 修复：数据位转换（直接用数字值，兼容所有版本）
    def _convert_databits(self, databits_str):
        databits_map = {
            '5': 5,  # FIVEBITS = 5
            '6': 6,  # SIXBITS = 6
            '7': 7,  # SEVENBITS = 7
            '8': 8   # EIGHTBITS = 8
        }
        return databits_map.get(databits_str, 8)  # 默认8位

    def _convert_stopbits(self, stopbits_str):
        stopbits_map = {
            '1': 1,  # STOPBITS_ONE = 1
            '2': 2   # STOPBITS_TWO = 2
        }
        return stopbits_map.get(stopbits_str, 1)  # 默认1位

    def _convert_parity(self, parity_str):
        """转换校验位（直接用字符值，兼容所有版本）"""
        parity_map = {
            'None': 'N',  # PARITY_NONE = 'N'
            'Odd': 'O',    # PARITY_ODD = 'O'
            'Even': 'E'    # PARITY_EVEN = 'E'
        }
        return parity_map.get(parity_str, 'N')  # 默认无校验
    def _open_serial(self):
        """打开串口（修复参数转换）"""
        if self.is_serial_open:
            self._append_receive_text(f"{self.system_tag}串口已打开！\n", "system")
            return

        try:
            port = self.current_selected_port if self.current_selected_port else 'None'
            if port == 'None':
                display_text = self.serial_list_combo.get()
                port = self.port_display_map.get(display_text, 'None')

            if port == 'None':
                self._append_receive_text(f"{self.system_tag}请选择有效的串口！\n", "system")
                return

            baudrate = int(self.baud_rate_combo.get())
            databits = self._convert_databits(self.serial_data_bits_combo.get())
            stopbits = self._convert_stopbits(self.serial_stop_bits_combo.get())
            parity = self._convert_parity(self.serial_parity_combo.get())

            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=databits,
                stopbits=stopbits,
                parity=parity,
                timeout=0.1
            )
            print(f"⚒️ 打开串口: {self.serial_port.get_settings()}")
            self.is_serial_open = True
            self._append_receive_text(f"⚒️ 成功打开串口: {port} 波特率: {baudrate}\n", "system")
            
            self.receive_thread = threading.Thread(target=self._receive_data, daemon=True)
            self.receive_thread.start()

        except Exception as e:
            self._append_receive_text(f"🩻 打开串口失败: {str(e)}\n", "error")
            self.is_serial_open = False
            self.serial_port = None

    def _close_serial(self):
        """关闭串口"""
        if not self.is_serial_open:
            #self._append_receive_text(f"{self.system_tag}串口未打开！\n", "system")
            self._system_message(f"{self.system_tag}串口未打开！", "system")
            return

        try:
            self.timer_running = False
            if self.timer_thread and self.timer_thread.is_alive():
                self.timer_thread.join(timeout=1)
            
            if self.serial_port:
                self.serial_port.close()
            
            self.is_serial_open = False
            port = self.current_selected_port if self.current_selected_port else '未知串口'
            self._append_receive_text(f"{self.system_tag}已关闭串口: {port}\n", "system")
            
        except Exception as e:
            self._append_receive_text(f"{self.system_tag}关闭串口失败: {str(e)}\n", "error")

    def _receive_data(self):
        """接收串口数据"""
        receive_buffer = ""
        while self.is_serial_open:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    raw_data = self.serial_port.read(self.serial_port.in_waiting)
                    data = raw_data.decode('utf-8', errors='replace')
                    if data:
                        if not self.debug_mode_var.get():
                            self._append_receive_text(data, "receive")
                        else:
                            receive_buffer += data
                            while '\n' in receive_buffer:
                                line, receive_buffer = receive_buffer.split('\n', 1)
                                line = line.strip()
                                if not line:
                                    continue
                                lower_line = line.lower()
                                match_key = "default"
                                for key in self.debug_color_dict:
                                    if key != "default" and key in lower_line:
                                        match_key = key
                                        break
                                self._append_receive_text(line + "\n", match_key)
                    if self.is_receive_bottom_track:
                        self.text_widget.see("end")
                time.sleep(0.01)
            except Exception as e:
                if self.is_serial_open:
                    self._append_receive_text(f"{self.system_tag}接收数据出错: {str(e)}\n", "error")
                break

    def _append_receive_text(self, text, tag=None):
        self._configure_text_tags()
        self.text_widget.insert(tk.END, text, tag)

    def _send_data(self):
        """发送数据"""
        if not self.is_serial_open:
            self._system_message(f"{self.system_tag}请先打开串口！", "error")
            return
        else:
            self._system_message(f"", "error")
        try:
            send_data = self.serial_send_data_text.get("1.0", tk.END).rstrip('\n')
            
            if not send_data:
                self._append_receive_text(f"{self.system_tag}发送数据不能为空！\n", "system")
                return
            
            if self.auto_newline_var.get():
                send_data += '\n'
            
            self.serial_port.write(send_data.encode('utf-8'))
            self._append_receive_text(f"⭐ {send_data}\n", "send")
            
        except Exception as e:
            self._append_receive_text(f"{self.system_tag}发送数据失败: {str(e)}\n", "error")

    def _clear_receive(self):
        """清空接收框（修复索引）"""
        self.text_widget.delete("1.0", tk.END)
        self._system_message("接收框已清空", "system")

    def _clear_send(self):
        """清空发送框（修复索引）"""
        self.serial_send_data_text.delete("1.0", tk.END)
        self._system_message("发送框已清空", "system")

    def _toggle_timer_send(self):
        """切换定时发送"""
        if self.timer_send_var.get():
            if not self.is_serial_open:
                self._system_message("请先打开串口再开启定时发送！", "error")
                self.timer_send_var.set(False)
                return
            
            self.timer_running = True
            self.timer_thread = threading.Thread(target=self._timer_send_loop, daemon=True)
            self.timer_thread.start()
            self._system_message("定时发送已开启", "system")
        else:
            self.timer_running = False
            if self.timer_thread and self.timer_thread.is_alive():
                self.timer_thread.join(timeout=1)
            self._system_message("定时发送已关闭", "system")

    def _timer_send_loop(self):
        """定时发送循环"""
        while self.timer_running and self.is_serial_open:
            try:
                interval = int(self.timer_value.get())
                if interval < 100:
                    interval = 100
                    self.timer_value.set("100")
                
                self._send_data()
                time.sleep(interval / 1000)
                
            except ValueError:
                self._system_message("定时周期必须是数字！", "error")
                self.timer_running = False
                self.timer_send_var.set(False)
                break
            except Exception as e:
                self._system_message(f"定时发送出错: {str(e)}", "error")
                self.timer_running = False
                self.timer_send_var.set(False)
                break

    def right_click_event(self, event):
        """ 接收框框被右击 """
        self.is_receive_bottom_track = not self.is_receive_bottom_track
    def ctrl_scroll_increase_font(self, event):
        """Ctrl + 鼠标滚轮向上 → 增大字体"""
        """Ctrl + 鼠标滚轮向下 → 减小字体"""
        try:
            current_font = self.serial_info_show_entry.cget("font")
            font_size = list(current_font)
            if event.delta > 0:
                if font_size[1] < 30:
                    font_size[1] += 1
            else:
                if font_size[1] > 7:
                    font_size[1] -= 1
            new_size = tuple(font_size)
            self.serial_info_show_entry.configure(font = new_size)
        except Exception as e:
            print("字体调整失败:", e)
    def _system_message(self, message, tag):
        self.system_tip_label.configure(
            text_color = "purple",
            text=f"{message}",
        )

    def run(self):
        """运行应用"""
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.mainloop()

    def _on_closing(self):
        """窗口关闭处理"""
        self.auto_scan_running = False
        if self.auto_scan_thread and self.auto_scan_thread.is_alive():
            self.auto_scan_thread.join(timeout=1)
        
        if self.is_serial_open:
            self._close_serial()
        
        self.destroy()

if __name__ == '__main__':
    ctk.set_default_color_theme("blue")
    app = SerialTool()
    app.run()