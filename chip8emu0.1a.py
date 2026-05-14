"""
mewchip8_tk.py
A small CHIP-8 emulator using Tkinter.

Requested style/features:
- Engine class name: mewchip8
- Tkinter UI
- 60 FPS display/timer loop
- Speed preset: chip8
- Blue hue graphics and UI text
- Black button backgrounds
- Window title: ac's chip 8 emu 0.1.1
- Window size: 600x400

Run:
    python mewchip8_tk.py

Then click "load rom" and pick a .ch8/.rom file.
"""

from __future__ import annotations

import random
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox


class mewchip8:
    """Minimal CHIP-8 engine."""

    WIDTH = 64
    HEIGHT = 32
    RAM_SIZE = 4096
    ROM_START = 0x200
    FONT_START = 0x050

    FONTSET = [
        0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
        0x20, 0x60, 0x20, 0x20, 0x70,  # 1
        0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
        0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
        0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
        0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
        0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
        0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
        0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
        0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
        0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
        0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
        0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
        0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
        0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
        0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
    ]

    def __init__(self) -> None:
        self.rom_path: Path | None = None
        self.reset(keep_rom=False)

    def reset(self, keep_rom: bool = True) -> None:
        self.memory = [0] * self.RAM_SIZE
        for i, byte in enumerate(self.FONTSET):
            self.memory[self.FONT_START + i] = byte

        self.v = [0] * 16
        self.i = 0
        self.pc = self.ROM_START
        self.stack: list[int] = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.keys = [False] * 16
        self.display = [0] * (self.WIDTH * self.HEIGHT)
        self.draw_flag = True
        self.loaded = False
        self.last_error = ""

        path = self.rom_path if keep_rom else None
        self.rom_path = path
        if path is not None:
            self.load_rom(path)

    def load_rom(self, path: str | Path) -> None:
        path = Path(path)
        data = path.read_bytes()
        max_rom = self.RAM_SIZE - self.ROM_START
        if len(data) > max_rom:
            raise ValueError(f"ROM is too large: {len(data)} bytes; max is {max_rom} bytes")

        # Keep fonts and registers reset, then copy ROM into memory at 0x200.
        saved_path = path
        self.rom_path = None
        self.reset(keep_rom=False)
        self.rom_path = saved_path
        for offset, byte in enumerate(data):
            self.memory[self.ROM_START + offset] = byte
        self.loaded = True
        self.draw_flag = True

    def set_key(self, key_index: int, pressed: bool) -> None:
        if 0 <= key_index < 16:
            self.keys[key_index] = pressed

    def tick_timers(self) -> None:
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1

    def step(self) -> None:
        if not self.loaded:
            return
        if self.pc < 0 or self.pc + 1 >= self.RAM_SIZE:
            self.last_error = f"PC out of range: {self.pc:03X}"
            return

        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc = (self.pc + 2) & 0xFFFF

        nnn = opcode & 0x0FFF
        nn = opcode & 0x00FF
        n = opcode & 0x000F
        x = (opcode >> 8) & 0x000F
        y = (opcode >> 4) & 0x000F
        top = opcode & 0xF000

        if opcode == 0x00E0:  # CLS
            self.display = [0] * (self.WIDTH * self.HEIGHT)
            self.draw_flag = True

        elif opcode == 0x00EE:  # RET
            if not self.stack:
                self.last_error = "Stack underflow on RET"
                return
            self.pc = self.stack.pop()

        elif top == 0x0000:  # SYS addr; ignored on modern interpreters
            pass

        elif top == 0x1000:  # JP addr
            self.pc = nnn

        elif top == 0x2000:  # CALL addr
            self.stack.append(self.pc)
            self.pc = nnn

        elif top == 0x3000:  # SE Vx, byte
            if self.v[x] == nn:
                self.pc += 2

        elif top == 0x4000:  # SNE Vx, byte
            if self.v[x] != nn:
                self.pc += 2

        elif top == 0x5000 and n == 0:  # SE Vx, Vy
            if self.v[x] == self.v[y]:
                self.pc += 2

        elif top == 0x6000:  # LD Vx, byte
            self.v[x] = nn

        elif top == 0x7000:  # ADD Vx, byte
            self.v[x] = (self.v[x] + nn) & 0xFF

        elif top == 0x8000:
            if n == 0x0:  # LD Vx, Vy
                self.v[x] = self.v[y]
            elif n == 0x1:  # OR Vx, Vy
                self.v[x] |= self.v[y]
            elif n == 0x2:  # AND Vx, Vy
                self.v[x] &= self.v[y]
            elif n == 0x3:  # XOR Vx, Vy
                self.v[x] ^= self.v[y]
            elif n == 0x4:  # ADD Vx, Vy
                total = self.v[x] + self.v[y]
                self.v[0xF] = 1 if total > 0xFF else 0
                self.v[x] = total & 0xFF
            elif n == 0x5:  # SUB Vx, Vy
                self.v[0xF] = 1 if self.v[x] >= self.v[y] else 0
                self.v[x] = (self.v[x] - self.v[y]) & 0xFF
            elif n == 0x6:  # SHR Vx
                self.v[0xF] = self.v[x] & 0x1
                self.v[x] = (self.v[x] >> 1) & 0xFF
            elif n == 0x7:  # SUBN Vx, Vy
                self.v[0xF] = 1 if self.v[y] >= self.v[x] else 0
                self.v[x] = (self.v[y] - self.v[x]) & 0xFF
            elif n == 0xE:  # SHL Vx
                self.v[0xF] = (self.v[x] >> 7) & 0x1
                self.v[x] = (self.v[x] << 1) & 0xFF
            else:
                self.last_error = f"Unknown opcode: {opcode:04X}"

        elif top == 0x9000 and n == 0:  # SNE Vx, Vy
            if self.v[x] != self.v[y]:
                self.pc += 2

        elif top == 0xA000:  # LD I, addr
            self.i = nnn

        elif top == 0xB000:  # JP V0, addr
            self.pc = (nnn + self.v[0]) & 0xFFFF

        elif top == 0xC000:  # RND Vx, byte
            self.v[x] = random.randint(0, 255) & nn

        elif top == 0xD000:  # DRW Vx, Vy, nibble
            self._draw_sprite(self.v[x], self.v[y], n)

        elif top == 0xE000:
            key = self.v[x] & 0xF
            if nn == 0x9E:  # SKP Vx
                if self.keys[key]:
                    self.pc += 2
            elif nn == 0xA1:  # SKNP Vx
                if not self.keys[key]:
                    self.pc += 2
            else:
                self.last_error = f"Unknown opcode: {opcode:04X}"

        elif top == 0xF000:
            if nn == 0x07:  # LD Vx, DT
                self.v[x] = self.delay_timer
            elif nn == 0x0A:  # LD Vx, K
                pressed_key = next((idx for idx, pressed in enumerate(self.keys) if pressed), None)
                if pressed_key is None:
                    self.pc -= 2
                else:
                    self.v[x] = pressed_key
            elif nn == 0x15:  # LD DT, Vx
                self.delay_timer = self.v[x]
            elif nn == 0x18:  # LD ST, Vx
                self.sound_timer = self.v[x]
            elif nn == 0x1E:  # ADD I, Vx
                self.i = (self.i + self.v[x]) & 0x0FFF
            elif nn == 0x29:  # LD F, Vx
                self.i = self.FONT_START + (self.v[x] & 0xF) * 5
            elif nn == 0x33:  # LD B, Vx
                value = self.v[x]
                self.memory[self.i] = value // 100
                self.memory[self.i + 1] = (value // 10) % 10
                self.memory[self.i + 2] = value % 10
            elif nn == 0x55:  # LD [I], V0..Vx
                for reg in range(x + 1):
                    self.memory[self.i + reg] = self.v[reg]
            elif nn == 0x65:  # LD V0..Vx, [I]
                for reg in range(x + 1):
                    self.v[reg] = self.memory[self.i + reg]
            else:
                self.last_error = f"Unknown opcode: {opcode:04X}"

        else:
            self.last_error = f"Unknown opcode: {opcode:04X}"

        self.pc &= 0xFFFF

    def _draw_sprite(self, x_pos: int, y_pos: int, rows: int) -> None:
        self.v[0xF] = 0
        for row in range(rows):
            sprite_byte = self.memory[self.i + row]
            for bit in range(8):
                if sprite_byte & (0x80 >> bit):
                    x = (x_pos + bit) % self.WIDTH
                    y = (y_pos + row) % self.HEIGHT
                    idx = y * self.WIDTH + x
                    if self.display[idx] == 1:
                        self.v[0xF] = 1
                    self.display[idx] ^= 1
        self.draw_flag = True


class MewChip8App:
    FPS = 60
    SCALE = 8
    CYCLES_PER_FRAME = 10  # 10 * 60 = 600 instructions/sec, a friendly CHIP-8 speed.

    BG = "#02060f"
    PANEL_BG = "#040b18"
    CANVAS_BG = "#000000"
    PIXEL = "#1e90ff"
    TEXT = "#5fb3ff"
    BUTTON_BG = "#000000"
    BUTTON_FG = "#227bff"
    BUTTON_ACTIVE = "#061c3a"

    KEYMAP = {
        "1": 0x1, "2": 0x2, "3": 0x3, "4": 0xC,
        "q": 0x4, "w": 0x5, "e": 0x6, "r": 0xD,
        "a": 0x7, "s": 0x8, "d": 0x9, "f": 0xE,
        "z": 0xA, "x": 0x0, "c": 0xB, "v": 0xF,
    }

    def __init__(self) -> None:
        self.engine = mewchip8()
        self.running = False
        self.next_frame_time = time.perf_counter()

        self.root = tk.Tk()
        self.root.title("ac's chip 8 emu 0.1.1")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG)

        self._build_ui()
        self._bind_keys()
        self._render()
        self._loop()

    def _build_ui(self) -> None:
        title = tk.Label(
            self.root,
            text="mewchip8  |  speed: chip8  |  60 fps",
            fg=self.TEXT,
            bg=self.BG,
            font=("Consolas", 12, "bold"),
        )
        title.pack(pady=(8, 4))

        self.canvas = tk.Canvas(
            self.root,
            width=self.engine.WIDTH * self.SCALE,
            height=self.engine.HEIGHT * self.SCALE,
            bg=self.CANVAS_BG,
            highlightthickness=2,
            highlightbackground=self.PIXEL,
        )
        self.canvas.pack()

        controls = tk.Frame(self.root, bg=self.PANEL_BG)
        controls.pack(fill="x", padx=44, pady=10)

        for label, command in [
            ("load rom", self.load_rom),
            ("start / pause", self.toggle_running),
            ("reset", self.reset_rom),
        ]:
            tk.Button(
                controls,
                text=label,
                command=command,
                fg=self.BUTTON_FG,
                bg=self.BUTTON_BG,
                activeforeground=self.TEXT,
                activebackground=self.BUTTON_ACTIVE,
                relief="flat",
                bd=0,
                padx=14,
                pady=6,
                font=("Consolas", 10, "bold"),
            ).pack(side="left", expand=True, padx=6, pady=8)

        self.status = tk.Label(
            self.root,
            text="load a CHIP-8 ROM to begin",
            fg=self.TEXT,
            bg=self.BG,
            font=("Consolas", 9),
        )
        self.status.pack(pady=(0, 3))

        help_text = "keys: 1234 / qwer / asdf / zxcv map to CHIP-8 keypad"
        tk.Label(
            self.root,
            text=help_text,
            fg=self.TEXT,
            bg=self.BG,
            font=("Consolas", 8),
        ).pack()

    def _bind_keys(self) -> None:
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_key_press(self, event: tk.Event) -> None:
        key = str(event.keysym).lower()
        if key in self.KEYMAP:
            self.engine.set_key(self.KEYMAP[key], True)

    def _on_key_release(self, event: tk.Event) -> None:
        key = str(event.keysym).lower()
        if key in self.KEYMAP:
            self.engine.set_key(self.KEYMAP[key], False)

    def load_rom(self) -> None:
        path = filedialog.askopenfilename(
            title="choose a CHIP-8 rom",
            filetypes=[
                ("CHIP-8 ROMs", "*.ch8 *.rom *.bin *.c8"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            self.engine.load_rom(path)
        except Exception as exc:  # Keep UI alive for bad files.
            messagebox.showerror("mewchip8", str(exc))
            return
        self.running = True
        self.status.config(text=f"running: {Path(path).name}")
        self._render()

    def toggle_running(self) -> None:
        if not self.engine.loaded:
            self.status.config(text="no rom loaded")
            return
        self.running = not self.running
        self.status.config(text="running" if self.running else "paused")

    def reset_rom(self) -> None:
        if self.engine.rom_path is None:
            self.engine.reset(keep_rom=False)
            self.running = False
            self.status.config(text="reset; no rom loaded")
        else:
            self.engine.reset(keep_rom=True)
            self.running = True
            self.status.config(text=f"reset: {self.engine.rom_path.name}")
        self._render()

    def _loop(self) -> None:
        now = time.perf_counter()
        if now >= self.next_frame_time:
            self.next_frame_time += 1.0 / self.FPS
            self._frame()
            # Avoid spiraling if the app stalls for a while.
            if self.next_frame_time < now - 0.25:
                self.next_frame_time = now + 1.0 / self.FPS

        delay_ms = max(1, int((self.next_frame_time - time.perf_counter()) * 1000))
        self.root.after(delay_ms, self._loop)

    def _frame(self) -> None:
        if self.running and self.engine.loaded:
            self.engine.last_error = ""
            for _ in range(self.CYCLES_PER_FRAME):
                self.engine.step()
                if self.engine.last_error:
                    self.running = False
                    self.status.config(text=self.engine.last_error)
                    break
            self.engine.tick_timers()

        if self.engine.draw_flag:
            self._render()
            self.engine.draw_flag = False

    def _render(self) -> None:
        self.canvas.delete("all")
        s = self.SCALE
        for y in range(self.engine.HEIGHT):
            row = y * self.engine.WIDTH
            for x in range(self.engine.WIDTH):
                if self.engine.display[row + x]:
                    self.canvas.create_rectangle(
                        x * s,
                        y * s,
                        (x + 1) * s,
                        (y + 1) * s,
                        fill=self.PIXEL,
                        outline=self.PIXEL,
                    )

    def _on_close(self) -> None:
        self.running = False
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    try:
        MewChip8App().run()
    except KeyboardInterrupt:
        sys.exit(0)
