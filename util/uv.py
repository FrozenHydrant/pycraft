import os
from PIL import Image

class TexturesAndUV:
    BASE_UVS = [(0.02, 0.02),
                (0.98, 0.02),
                (0.02, 0.98),
                (0.02, 0.98),
                (0.98, 0.02),
                (0.98, 0.98)]
    
    def __init__(self):
        self.atlas = None
        self.uv_mapping = {}
        texture_loc = os.path.join(os.getcwd(), "textures")

        for _, _, images in os.walk(texture_loc):
            height = 16
            width = 16 * len(images)
            width_frac = 1 / len(images)
            index = 0
            composite = Image.new('RGBA', (width, height))
            for image_s in images:
                canon_name = image_s.split(".")[0]
                # Map uvs
                current_uvs = []
                for uv in TexturesAndUV.BASE_UVS:
                    new_uv = ((index + uv[0]) * width_frac, uv[1])
                    current_uvs.append(new_uv)
                # Join images
                image_path = os.path.join(texture_loc, image_s)
                img = Image.open(image_path).convert('RGBA')
                composite.paste(img, (index*16, 0))
                self.uv_mapping[canon_name] = current_uvs
                
                index += 1
            self.atlas = composite
            self.atlas.save("atlas.png")

    def get_uvs(self):
        return self.uv_mapping

    def get_texture_atlas(self):
        return self.atlas