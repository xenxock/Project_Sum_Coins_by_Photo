import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, font
from PIL import Image, ImageTk

COIN_DIAMETERS = {
    1:   20.5,
    2:   23.0,
    5:   25.0,
    10:  22.0
}

def get_coin_denomination(diameter_mm, diameters_map):
    tolerance = 1.5  # мм
    best_match = None
    min_diff = float('inf')
    for value, ref_diameter in diameters_map.items():
        diff = abs(diameter_mm - ref_diameter)
        if diff < min_diff and diff < tolerance:
            min_diff = diff
            best_match = value
    return best_match

def show_results_window(parent_window, image_cv, total_sum):
    result_window = tk.Toplevel(parent_window)
    result_window.title("Результат подсчёта")
    result_window.configure(bg="#f0f0f0")
    result_window.protocol("WM_DELETE_WINDOW", parent_window.destroy)

    header_font = font.Font(family="Helvetica", size=16, weight="bold")
    sum_label = tk.Label(
        result_window,
        text=f"Общая сумма: {total_sum:.2f} руб.",
        font=header_font, pady=10, bg="#f0f0f0", fg="#333"
    )
    sum_label.pack()

    rgb_image = cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb_image)
    pil_image.thumbnail((800, 600), Image.Resampling.LANCZOS)
    tk_image = ImageTk.PhotoImage(pil_image)

    image_label = tk.Label(result_window, image=tk_image)
    image_label.pack(padx=10, pady=10)
    image_label.image = tk_image

    result_window.wait_window()

def segment_and_separate(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=2)

    sure_bg = cv2.dilate(closed, kernel, iterations=3)

    dist_transform = cv2.distanceTransform(closed, cv2.DIST_L2, 5)
    _, sure_fg = cv2.threshold(dist_transform, 0.5 * dist_transform.max(), 255, 0)
    sure_fg = np.uint8(sure_fg)

    unknown = cv2.subtract(sure_bg, sure_fg)

    num_markers, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0
    image_for_ws = image.copy()
    cv2.watershed(image_for_ws, markers)

    circles = []
    for label in range(2, num_markers + 2):
        mask = np.uint8(markers == label)
        if cv2.countNonZero(mask) < 400:
            continue
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        cnt = max(cnts, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if area < 400:
            continue
        (x, y), r = cv2.minEnclosingCircle(cnt)
        if r < 8:
            continue
        circles.append((int(x), int(y), int(r)))
    return circles

def process_image(root, image_path):
    try:
        n = np.fromfile(image_path, np.uint8)
        image = cv2.imdecode(n, cv2.IMREAD_COLOR)
    except Exception:
        image = None

    if image is None:
        messagebox.showerror("Ошибка", "Не удалось загрузить изображение.")
        root.deiconify()
        return

    root.withdraw()

    try:
        circles = segment_and_separate(image)
    except Exception as e:
        messagebox.showerror("Ошибка обработки", f"Сегментация не удалась:\n{e}")
        root.destroy()
        return

    if not circles:
        messagebox.showinfo("Результат", "На изображении не найдено монет.")
        root.destroy()
        return

    largest_circle = max(circles, key=lambda c: c[2])
    largest_radius_px = largest_circle[2]

    largest_coin_value = simpledialog.askfloat(
        "Калибровка",
        f"Найден самый большой круг (r = {largest_radius_px}px). Введите его номинал (целое число):",
        parent=root
    )
    if largest_coin_value is None or largest_coin_value not in COIN_DIAMETERS:
        messagebox.showerror("Ошибка", "Отмена или неверный номинал.")
        root.destroy()
        return

    largest_coin_diameter_mm = COIN_DIAMETERS[largest_coin_value]
    pixels_to_mm_ratio = largest_coin_diameter_mm / (largest_radius_px * 2)

    total_sum = 0.0
    output_image = image.copy()

    for (x, y, r) in circles:
        diameter_mm = (r * 2) * pixels_to_mm_ratio
        denomination = get_coin_denomination(diameter_mm, COIN_DIAMETERS)
        if denomination is not None:
            total_sum += denomination
            cv2.circle(output_image, (x, y), r, (0, 220, 0), 2)
            label = f"{denomination:.2f}".replace('.', ',')
            cv2.putText(
                output_image, label, (int(x - r/2), int(y + r/4)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA
            )
        else:
            cv2.circle(output_image, (x, y), r, (0, 0, 220), 2)

    show_results_window(root, output_image, total_sum)

def main():
    root = tk.Tk()
    root.title("Счётчик монет")
    root.geometry("360x200")
    root.configure(bg="#f0f0f0")

    main_font = font.Font(family="Helvetica", size=11)
    button_font = font.Font(family="Helvetica", size=12, weight="bold")

    def select_image():
        file_path = filedialog.askopenfilename(
            title="Выберите изображение с монетами",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )
        if file_path:
            process_image(root, file_path)

    label = tk.Label(
        root,
        text="Загрузите фото с монетами для подсчёта суммы.",
        wraplength=340, font=main_font, bg="#f0f0f0"
    )
    label.pack(pady=20, padx=10)

    load_button = tk.Button(
        root, text="Выбрать файл", command=select_image,
        font=button_font, bg="#007bff", fg="white", pady=10, width=22
    )
    load_button.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()