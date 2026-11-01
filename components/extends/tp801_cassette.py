"""TP801 Kansas City 300-baud cassette images (PCM WAV and Intel HEX)."""
# The codec below is adapted from this workspace's tp801/cassette.py.
from array import array
from pathlib import Path
import math
import struct
import wave

RATE = 9600
BIT_SAMPLES = RATE // 300


def records(memory, start, end):
    if not 0 <= start <= end <= 0xffff: raise ValueError('磁带起止地址无效')
    def line(address, kind, data):
        data=bytes(data)
        raw=bytes([len(data),address >> 8,address & 255,kind])+data
        return ':'+(raw+bytes([(-sum(raw)) & 255])).hex().upper()+'\r\n'
    result=[]
    for pos in range(start,end+1,16):
        result.append(line(pos,0,(memory(a) for a in range(pos,min(pos+16,end+1)))))
    result.append(line(0,1,()))
    return ''.join(result)


def parse_records(text):
    image={}; position=0; eof=False
    while True:
        colon=text.find(':',position)
        if colon<0:break
        try:
            count=int(text[colon+1:colon+3],16)
            length=(count+5)*2
            field=text[colon+1:colon+1+length]
            if len(field)!=length:raise ValueError('记录不完整')
            raw=bytes.fromhex(field)
            if len(raw)!=count+5 or sum(raw)&255:raise ValueError('记录校验和错误')
            address=(raw[1]<<8)|raw[2];kind=raw[3]
            if kind==0:
                if address+count>65536:raise ValueError('记录超出地址空间')
                for i,value in enumerate(raw[4:-1]):
                    if address+i in image:raise ValueError('记录地址重叠')
                    image[address+i]=value
            elif kind==1:
                if count or address:raise ValueError('结束记录无效')
                eof=True;break
            else:raise ValueError('磁带只支持 00 数据和 01 结束记录')
            position=colon+1+length
        except (ValueError,IndexError) as error:raise ValueError(f'Intel HEX 记录无效：{error}') from error
    if not eof:raise ValueError('磁带缺少有效的结束记录')
    return image


def write_wav(path, text, leader_seconds=40, trailer_seconds=5):
    try:payload=text.encode('ascii')
    except UnicodeEncodeError as error:raise ValueError('磁带记录必须为 ASCII') from error
    waves=[]
    for frequency in (1200,2400):
        values=[round(22000*math.sin(2*math.pi*frequency*i/RATE)) for i in range(BIT_SAMPLES)]
        waves.append(struct.pack('<'+'h'*BIT_SAMPLES,*values))
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(RATE)
        chunk=waves[1]*300
        for _ in range(leader_seconds):out.writeframesraw(chunk)
        for byte in payload:
            bits=[0]+[(byte>>bit)&1 for bit in range(7)]+[1]
            out.writeframesraw(b''.join(waves[bit] for bit in bits))
        for _ in range(trailer_seconds):out.writeframesraw(chunk)


def read_wav(path):
    try:
        with wave.open(str(path),'rb') as inp:
            channels=inp.getnchannels();width=inp.getsampwidth();rate=inp.getframerate()
            if inp.getcomptype()!='NONE' or channels not in (1,2) or width not in (1,2,3,4):
                raise ValueError('仅支持单声道或立体声的 8/16/24/32 位整数 PCM WAV')
            if not 8000<=rate<=192000:raise ValueError('WAV 采样率不受支持')
            raw=inp.readframes(inp.getnframes())
    except (wave.Error,EOFError) as error:raise ValueError(f'WAV 格式错误：{error}') from error
    if width==1: samples=[x-128 for x in raw]
    elif width==3:
        if len(raw)%3: raise ValueError('WAV 采样数据不完整')
        samples=[int.from_bytes(raw[i:i+3],'little',signed=True) for i in range(0,len(raw),3)]
    else:
        samples=array('h' if width==2 else 'i');samples.frombytes(raw)
        import sys
        if sys.byteorder!='little':samples.byteswap()
    if channels==2:samples=[(samples[i]+samples[i+1])//2 for i in range(0,len(samples)-1,2)]
    if len(samples)<rate//10:raise ValueError('WAV 太短')
    # Prefix sums allow a full frame to be classified in O(1) per bit.
    edges=array('I',[0]);last=samples[0]>=0;total=0
    for sample in samples:
        state=sample>=0
        if state!=last:total+=1;last=state
        edges.append(total)
    bitlen=rate/300.0
    for phase in range(max(1,round(bitlen))):
        def bit(index):
            a=round(phase+index*bitlen);b=round(phase+(index+1)*bitlen)
            return int(edges[b]-edges[a]>=12) if b<len(edges) else None
        count=int((len(samples)-phase)//bitlen);i=0;ones=0
        while i<count:
            b=bit(i)
            if b==1:ones+=1;i+=1;continue
            if ones>=16:break
            ones=0;i+=1
        if i>=count:continue
        decoded=bytearray()
        while i+8<count:
            if bit(i)!=0:i+=1;continue
            value=sum(bit(i+1+n)<<n for n in range(7))
            if bit(i+8)!=1:break
            decoded.append(value);i+=9
        text=decoded.decode('ascii',errors='ignore')
        try:return parse_records(text)
        except ValueError:continue
    raise ValueError('未识别到有效的 TP801 300 波特磁带记录或校验失败')


class TP801Cassette:
    """File-level TP801 cassette adapter; the host supplies memory callbacks.

    The machine connects request_load/request_save to the appropriate monitor
    command. Transfers are decoded/encoded as WAV files, not as CPU pins.
    `write_batch` must validate the full mapping before changing memory.
    """
    name = 'TP801 磁带'
    pins = {'EAR': 'output', 'MIC': 'input', 'REMOTE': 'input'}

    def __init__(self, read_byte, write_batch, capture_range):
        if not all(callable(fn) for fn in (read_byte, write_batch, capture_range)):
            raise TypeError('磁带内存和地址范围回调必须可调用')
        self.read_byte = read_byte
        self.write_batch = write_batch
        self.capture_range = capture_range
        self.root = None
        self.pause = lambda: None
        self._window = None
        self._status = None
        self.status = '空闲'

    def bind_ui(self, root, pause):
        self.root, self.pause = root, pause

    def _set_status(self, value):
        self.status = value
        if self._status is not None and self._window is not None and self._window.winfo_exists():
            self._status.set(value)

    def open_gui(self, root, pause):
        import tkinter as tk
        from tkinter import ttk
        self.bind_ui(root, pause)
        window = tk.Toplevel(root); window.title(self.name)
        self._window = window
        self._status = tk.StringVar(master=window, value=self.status)
        ttk.Label(window, textvariable=self._status, padding=4).pack(anchor='w')
        buttons = ttk.Frame(window); buttons.pack(padx=4, pady=4)
        tk.Button(buttons, text='读取 WAV…', command=self.request_load).pack(side='left', padx=2)
        tk.Button(buttons, text='录制 WAV…', command=self.request_save).pack(side='left', padx=2)
        ttk.Label(window, text='支持 TP801 300 波特磁带 WAV', padding=4).pack(anchor='w')
        return window

    def request_load(self):
        if self.root is None: raise RuntimeError('请先将磁带连接到平台界面')
        self.pause()
        self.root.after_idle(self._choose_load)

    def request_save(self):
        if self.root is None: raise RuntimeError('请先将磁带连接到平台界面')
        self.pause()
        self.root.after_idle(self._choose_save)

    def _choose_load(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(parent=self.root, title='读取 TP801 磁带 WAV',
                                          filetypes=[('PCM WAV', '*.wav')])
        if not path: return
        try:
            image = read_wav(path)
            if not image: raise ValueError('磁带不包含数据记录')
            self.write_batch(image)
            self._set_status(f'读取完成：{len(image)} 字节')
        except (ValueError, OSError) as error:
            self._set_status('读取失败')
            messagebox.showerror('磁带读取失败', str(error), parent=self.root)

    def _choose_save(self):
        from tkinter import filedialog, messagebox
        import os
        import tempfile
        path = filedialog.asksaveasfilename(parent=self.root, title='录制 TP801 磁带 WAV',
                                            defaultextension='.wav', filetypes=[('PCM WAV', '*.wav')])
        if not path: return
        scratch = None
        try:
            start, end = self.capture_range()
            data = records(self.read_byte, start, end)
            destination = Path(path)
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.tp801-', suffix='.wav', delete=False) as temporary:
                scratch = Path(temporary.name)
            write_wav(scratch, data)
            os.replace(scratch, destination)
            self._set_status(f'录制完成：{start:04X}–{end:04X}')
        except (ValueError, OSError) as error:
            self._set_status('录制失败')
            messagebox.showerror('磁带录制失败', str(error), parent=self.root)
        finally:
            if scratch is not None and scratch.exists(): scratch.unlink()
