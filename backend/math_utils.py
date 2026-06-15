import math

def calculate_distance_2d(p1, p2):
    """Oblicza odległość 2D (X, Y) między dwoma punktami."""
    if not p1 or not p2:
        return 0.0
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def calculate_angle_2d(a, b, c):
    """
    Oblicza kąt (w stopniach) między trzema punktami 2D: a, b, c, 
    gdzie 'b' jest wierzchołkiem kąta.
    Zwraca wartość z zakresu [0, 180].
    """
    if not a or not b or not c:
        return 0.0

    # Wektory ba i bc
    ba_x = a.x - b.x
    ba_y = a.y - b.y
    
    bc_x = c.x - b.x
    bc_y = c.y - b.y
    
    # Iloczyn skalarny i długości wektorów
    dot_product = ba_x * bc_x + ba_y * bc_y
    mag_ba = math.sqrt(ba_x**2 + ba_y**2)
    mag_bc = math.sqrt(bc_x**2 + bc_y**2)
    
    if mag_ba == 0 or mag_bc == 0:
        return 0.0
        
    # Zabezpieczenie przed błędami precyzji float (np. cosinus > 1.0)
    cos_angle = dot_product / (mag_ba * mag_bc)
    cos_angle = max(-1.0, min(1.0, cos_angle))
    
    angle_rad = math.acos(cos_angle)
    return math.degrees(angle_rad)

def get_forehead_y(eyes_and_ears):
    """
    Oblicza współrzędną Y wirtualnego czoła na podstawie Y oczu lub uszu.
    Zwraca najmniejsze Y (czyli najwyższy punkt głowy z dostępnych).
    """
    valid_y = [p.y for p in eyes_and_ears if p and p.visibility > 0.5]
    if not valid_y:
        return 0.0
    # Im mniejsze Y, tym wyżej na ekranie. Czoło jest nieco wyżej niż oczy.
    # W uproszczeniu: bierzemy najwyższy punkt punkt (najmniejsze Y) i odejmujemy mały offset
    # lub traktujemy linię brwi/oczu jako przybliżenie, jeśli to wystarczy.
    return min(valid_y) - 0.05
