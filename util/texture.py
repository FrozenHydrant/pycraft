import moderngl

class SimpleImageTexture:
    def __init__(self, image):
        self.ctx = moderngl.get_context()

        self.texture = self.ctx.texture(image.size, 4, image.tobytes())
        self.sampler = self.ctx.sampler(texture=self.texture)

    def use(self):
        self.sampler.use()