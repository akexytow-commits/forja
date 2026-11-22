"""Métricas del equipo para /salud (RAM y disco libres) sin dependencias extra."""
from __future__ import annotations

import ctypes
import os
import shutil
from pathlib import Path


def ram_libre_mb() -> int | None:
    return _memoria("ullAvailPhys", "SC_AVPHYS_PAGES")


def ram_total_mb() -> int | None:
    return _memoria("ullTotalPhys", "SC_PHYS_PAGES")


def _memoria(campo: str, sysconf: str) -> int | None:
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(getattr(st, campo) / (1024 * 1024))
        return None
    try:
        return int(os.sysconf(sysconf) * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024))
    except (ValueError, OSError, AttributeError):
        return None


def disco_libre_mb(ruta: Path) -> int:
    return int(shutil.disk_usage(ruta).free / (1024 * 1024))


def ram_proceso_mb(pid: int | None = None) -> float | None:
    """Memoria residente (working set) de un proceso, en MB. TST-100 / NFR-002."""
    if os.name == "nt":
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(0x0410, False, pid) if pid else k32.GetCurrentProcess()   # QUERY_INFORMATION | VM_READ
        if not h:
            return None
        try:
            c = PMC()
            c.cb = ctypes.sizeof(PMC)
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
            if psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
                return round(c.WorkingSetSize / (1024 * 1024), 1)
            return None
        finally:
            if pid:
                k32.CloseHandle(ctypes.c_void_p(h))
    try:
        with open(f"/proc/{pid or 'self'}/status", encoding="ascii") as f:
            for linea in f:
                if linea.startswith("VmRSS:"):
                    return round(int(linea.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None
