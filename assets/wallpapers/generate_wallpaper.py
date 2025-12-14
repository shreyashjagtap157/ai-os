# AI-OS Default Wallpaper Generator
# Creates a procedural gradient wallpaper

from PIL import Image, ImageDraw
import math
import sys

def create_wallpaper(width=1920, height=1080, output="wallpaper.png"):
    """Generate AI-OS default wallpaper with gradient and subtle pattern"""
    
    # Create image
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # Colors
    color1 = (26, 26, 46)    # #1a1a2e
    color2 = (22, 33, 62)    # #16213e
    color3 = (102, 126, 234) # #667eea (accent)
    
    # Create diagonal gradient
    for y in range(height):
        for x in range(width):
            # Gradient factor (diagonal)
            t = (x / width + y / height) / 2
            
            # Interpolate colors
            r = int(color1[0] + (color2[0] - color1[0]) * t)
            g = int(color1[1] + (color2[1] - color1[1]) * t)
            b = int(color1[2] + (color2[2] - color1[2]) * t)
            
            # Add subtle noise/pattern
            noise = int(math.sin(x * 0.01) * 2 + math.cos(y * 0.01) * 2)
            r = max(0, min(255, r + noise))
            g = max(0, min(255, g + noise))
            b = max(0, min(255, b + noise))
            
            img.putpixel((x, y), (r, g, b))
    
    # Add subtle radial glow in center
    cx, cy = width // 2, height // 2
    max_dist = math.sqrt(cx**2 + cy**2)
    
    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            # Glow intensity (fades from center)
            glow = max(0, 1 - dist / (max_dist * 0.7))
            glow = glow ** 3 * 0.05  # Subtle
            
            current = img.getpixel((x, y))
            r = min(255, int(current[0] + color3[0] * glow))
            g = min(255, int(current[1] + color3[1] * glow))
            b = min(255, int(current[2] + color3[2] * glow))
            
            img.putpixel((x, y), (r, g, b))
    
    img.save(output)
    print(f"Wallpaper saved to {output}")

if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 1920
    h = int(sys.argv[2]) if len(sys.argv) > 2 else 1080
    out = sys.argv[3] if len(sys.argv) > 3 else "wallpaper.png"
    
    create_wallpaper(w, h, out)
