import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import sharp from "sharp";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const iconsDir = path.join(__dirname, "../public/icons");
const svgPath = path.join(iconsDir, "icon.svg");

const svg = fs.readFileSync(svgPath);

const sizes = [
  { name: "icon-72.png", size: 72 },
  { name: "icon-96.png", size: 96 },
  { name: "icon-128.png", size: 128 },
  { name: "icon-144.png", size: 144 },
  { name: "icon-152.png", size: 152 },
  { name: "icon-192.png", size: 192 },
  { name: "icon-384.png", size: 384 },
  { name: "icon-512.png", size: 512 },
  { name: "apple-touch-icon.png", size: 180 },
];

async function generate() {
  for (const { name, size } of sizes) {
    await sharp(svg).resize(size, size).png().toFile(path.join(iconsDir, name));
    console.log(`Generated ${name}`);
  }

  const maskableSize = 512;
  const inner = Math.round(maskableSize * 0.72);
  const padded = await sharp(svg)
    .resize(inner, inner)
    .extend({
      top: Math.floor((maskableSize - inner) / 2),
      bottom: Math.ceil((maskableSize - inner) / 2),
      left: Math.floor((maskableSize - inner) / 2),
      right: Math.ceil((maskableSize - inner) / 2),
      background: { r: 26, g: 39, b: 68, alpha: 1 },
    })
    .png()
    .toBuffer();

  await sharp(padded).toFile(path.join(iconsDir, "icon-maskable-512.png"));
  console.log("Generated icon-maskable-512.png");
}

generate().catch((err) => {
  console.error(err);
  process.exit(1);
});
