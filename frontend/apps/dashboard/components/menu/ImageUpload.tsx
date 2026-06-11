"use client";

import { useState, useRef } from "react";
import ReactCrop, { type Crop, centerCrop, makeAspectCrop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";
import type { Dish } from "@/lib/api";
import { getUploadUrl, confirmDishImage } from "@/lib/actions";

interface Props {
  venueId: string;
  dish: Dish;
  onClose: () => void;
  onSuccess: (imageUrl: string) => void;
}

export default function ImageUpload({ venueId, dish, onClose, onSuccess }: Props) {
  const [src, setSrc] = useState<string>("");
  const [crop, setCrop] = useState<Crop>();
  const [uploading, setUploading] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setSrc(reader.result as string);
    reader.readAsDataURL(file);
  }

  function onImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
    setCrop(centerCrop(makeAspectCrop({ unit: "%", width: 80 }, 1, w, h), w, h));
  }

  async function handleUpload() {
    if (!imgRef.current || !crop) return;
    setUploading(true);
    try {
      const img = imgRef.current;
      const scaleX = img.naturalWidth / img.width;
      const scaleY = img.naturalHeight / img.height;
      const canvas = document.createElement("canvas");
      canvas.width = 512;
      canvas.height = 512;
      canvas.getContext("2d")!.drawImage(
        img,
        (crop.x / 100) * img.width * scaleX,
        (crop.y / 100) * img.height * scaleY,
        (crop.width / 100) * img.width * scaleX,
        (crop.height / 100) * img.height * scaleY,
        0, 0, 512, 512
      );
      const blob = await new Promise<Blob>((res) => canvas.toBlob((b) => res(b!), "image/jpeg", 0.85));
      const { upload_url, image_url } = await getUploadUrl(venueId, dish.id);
      await fetch(upload_url, { method: "PUT", body: blob, headers: { "Content-Type": "image/jpeg" } });
      await confirmDishImage(venueId, dish.id, image_url);
      onSuccess(image_url);
      onClose();
    } catch {
      alert("Ошибка загрузки фото");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-gray-900">Фото: {dish.name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        {!src ? (
          <label className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:border-orange-400 transition-colors">
            <span className="text-sm text-gray-500 mb-1">Выберите фото</span>
            <span className="text-xs text-gray-400">JPG, PNG до 5 МБ</span>
            <input type="file" accept="image/*" onChange={onFile} className="hidden" />
          </label>
        ) : (
          <>
            <ReactCrop crop={crop} onChange={setCrop} aspect={1} className="max-h-72 rounded-lg overflow-hidden">
              <img ref={imgRef} src={src} onLoad={onImageLoad} alt="crop preview" className="max-w-full" />
            </ReactCrop>
            <div className="flex gap-3 mt-4">
              <button onClick={() => setSrc("")} className="flex-1 border border-gray-200 text-gray-700 py-2 rounded-lg text-sm font-medium hover:bg-gray-50">
                Другое фото
              </button>
              <button onClick={handleUpload} disabled={uploading} className="flex-1 bg-orange-500 text-white py-2 rounded-lg text-sm font-medium hover:bg-orange-600 disabled:opacity-60">
                {uploading ? "Загружаем..." : "Сохранить"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
