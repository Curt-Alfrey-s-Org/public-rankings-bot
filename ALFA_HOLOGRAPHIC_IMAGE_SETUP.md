# ALFa Holographic Image Setup

## Adding the Holographic ALFa Image to Home Page

The Home page now has a holographic-themed ALFa AI section with visual effects that match the futuristic aesthetic.

### To Add Your Custom ALFa Holographic Image:

1. **Save the image** to the Rankings-Bot frontend assets folder:
   ```
   Rankings-Bot/frontend/public/assets/alfa-holographic.jpg
   ```
   (or .png, .webp - any web image format)

2. **Uncomment the background image line** in `Rankings-Bot/frontend/src/pages/Home.tsx`:

   Find this line (around line 175):
   ```tsx
   {/* <div className="absolute inset-0 bg-cover bg-center opacity-30" style={{ backgroundImage: "url('/assets/alfa-holographic.jpg')" }}></div> */}
   ```

   Uncomment it to:
   ```tsx
   <div className="absolute inset-0 bg-cover bg-center opacity-30" style={{ backgroundImage: "url('/assets/alfa-holographic.jpg')" }}></div>
   ```

3. **Adjust opacity** if needed (change `opacity-30` to values like `opacity-20`, `opacity-40`, etc.)

### Current Design Features (without custom image):

✅ Holographic cyan/blue gradient theme
✅ Animated grid pattern background
✅ Glowing orbs and blur effects
✅ Pulsing robot emoji with glow
✅ Glass-morphism cards with hover effects
✅ Gradient text "ALFa AI Assistant"
✅ Smooth transitions and animations

The section already looks futuristic and matches the ALFa aesthetic - adding the image will enhance it further!

### Alternative: Use as Section Background

If you prefer the image more prominent, you can adjust the styling:
- Change `opacity-30` to `opacity-50` or higher
- Modify `bg-center` to `bg-right` to position the holographic figure on the right side
- Add `bg-no-repeat` if you want single image instead of tiled

