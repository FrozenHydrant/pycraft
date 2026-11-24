import moderngl
import glm

class Mesh:
    def __init__(self, program, geometry, texture):
        self.ctx = moderngl.get_context()
        self.vao = geometry.vertex_array(program)
        self.color = (1.0, 0.0, 0.0)
        self.transform = glm.mat4(1.0)
        self.texture = texture
        
    def change_me(self, transform):
        self.transform = transform
        return self

    def render(self):
        self.texture.use()
        self.vao.program['transform'].write(self.transform)
        self.vao.render()