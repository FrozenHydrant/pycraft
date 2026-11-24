import math
import os
import random
import sys
from enum import Enum
from PIL import Image
import glm
import moderngl
import numpy as np
import pygame
import noise

os.environ['SDL_WINDOWS_DPI_AWARENESS'] = 'permonitorv2'

pygame.init()
pygame.display.set_mode((800, 800), flags=pygame.OPENGL | pygame.DOUBLEBUF, vsync=True)


class SimpleImageTexture:
    def __init__(self, image):
        self.ctx = moderngl.get_context()

        self.texture = self.ctx.texture(image.size, 4, image.tobytes())
        self.sampler = self.ctx.sampler(texture=self.texture)

    def use(self):
        self.sampler.use()


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


class Cube:
    def __init__(self, program, transform, color, type):
        #Cube.PLANE_GEOMETRY = PlaneGeometry()
        self.transform = transform
        self.color = color
        self.meshes = []
        self.program = program
        self.type = type


class Blocks(Enum):
    GRASS_BLOCK = 0


class Sides(Enum):
    PIX = 0
    SID = 1
    SKY = 2
    WOR = 3
    BOT = 4
    TOP = 5


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
    

class ChunkGeometry:
    PIX_V = [(-0.5, -0.5, 0.5), 
            (-0.5, 0.5, 0.5),
            (-0.5, -0.5, -0.5),
            (-0.5, -0.5, -0.5),
            (-0.5, 0.5, 0.5),
            (-0.5, 0.5, -0.5)]
    SID_V = [(0.5, -0.5, 0.5), 
            (0.5, 0.5, 0.5),
            (0.5, -0.5, -0.5),
            (0.5, -0.5, -0.5),
            (0.5, 0.5, 0.5),
            (0.5, 0.5, -0.5)]
    SKY_V = [(0.5, -0.5, 0.5), 
            (-0.5, -0.5, 0.5),
            (0.5, -0.5, -0.5),
            (0.5, -0.5, -0.5),
            (-0.5, -0.5, 0.5),
            (-0.5, -0.5, -0.5)]
    WOR_V = [(0.5, 0.5, 0.5), 
            (-0.5, 0.5, 0.5),
            (0.5, 0.5, -0.5),
            (0.5, 0.5, -0.5),
            (-0.5, 0.5, 0.5),
            (-0.5, 0.5, -0.5)]
    BOT_V = [(-0.5, -0.5, -0.5), 
            (0.5, -0.5, -0.5),
            (-0.5, 0.5, -0.5),
            (-0.5, 0.5, -0.5),
            (0.5, -0.5, -0.5),
            (0.5, 0.5, -0.5)]
    TOP_V = [(-0.5, -0.5, 0.5), 
            (0.5, -0.5, 0.5),
            (-0.5, 0.5, 0.5),
            (-0.5, 0.5, 0.5),
            (0.5, -0.5, 0.5),
            (0.5, 0.5, 0.5)]  
    NORMALS = {Sides.PIX: (-1, 0, 0), Sides.SID: (1, 0, 0), Sides.SKY: (0, -1, 0), Sides.WOR: (0, 1, 0), Sides.BOT: (0, 0, -1), Sides.TOP: (0, 0, 1)}
    UVS = TexturesAndUV()
    TEXTURE = SimpleImageTexture(UVS.get_texture_atlas())
    UV_MAPPING = {(Sides.PIX, Blocks.GRASS_BLOCK): UVS.get_uvs()["grass_block_side"],
                  (Sides.SID, Blocks.GRASS_BLOCK): UVS.get_uvs()["grass_block_side"],
                  (Sides.SKY, Blocks.GRASS_BLOCK): UVS.get_uvs()["grass_block_side"],
                  (Sides.WOR, Blocks.GRASS_BLOCK): UVS.get_uvs()["grass_block_side"],
                  (Sides.BOT, Blocks.GRASS_BLOCK): UVS.get_uvs()["grass_block_top"],
                  (Sides.TOP, Blocks.GRASS_BLOCK): UVS.get_uvs()["grass_block_top"]}
    

    def __init__(self, blocks):
        self.ctx = moderngl.get_context()
        self.vbo = None

        my_vertices = []
        for i in range(16):
            for j in range(16):
                for k in range(16):
                    c_block: Cube = blocks[i][j][k]
                    if c_block is None:
                        continue

                    # Only add faces that are visible to the mesh
                    considered = []
                    if i == 0 or blocks[i - 1][j][k] is None:
                        considered.append((ChunkGeometry.PIX_V, Sides.PIX))
                    if i == 15 or blocks[i + 1][j][k] is None:
                        considered.append((ChunkGeometry.SID_V, Sides.SID))
                    if j == 0 or blocks[i][j - 1][k] is None:
                        considered.append((ChunkGeometry.SKY_V, Sides.SKY))
                    if j == 15 or blocks[i][j + 1][k] is None:
                        considered.append((ChunkGeometry.WOR_V, Sides.WOR))
                    if k == 0 or blocks[i][j][k - 1] is None:
                        considered.append((ChunkGeometry.BOT_V, Sides.BOT))
                    if k == 15 or blocks[i][j][k + 1] is None:
                        considered.append((ChunkGeometry.TOP_V, Sides.TOP))
                            
                    for verts, side in considered:
                        uvs = self.UV_MAPPING[(side, c_block.type)]
                        index = 0
                        for vert in verts:
                            transformed_vertex = glm.vec3(c_block.transform * glm.vec4(vert, 1.0))
                            # Unwrap and add (vertex / normal)
                            for elt in transformed_vertex:
                                my_vertices.append(elt)
                            for elt in ChunkGeometry.NORMALS[side]:
                                my_vertices.append(elt)

                            mix_col = (1, 1, 1)
                            if side == Sides.TOP and c_block.type == Blocks.GRASS_BLOCK:
                                mix_col = (0.3, 0.6, 0.05)
                            for elt in mix_col:
                                my_vertices.append(elt)

                            # Add UV info
                            for elt in uvs[index]:
                                my_vertices.append(elt)
                            index += 1
                    
        np_vertices = np.array(my_vertices).flatten()
        if np_vertices.shape[0] > 0:
            self.vbo = self.ctx.buffer(np_vertices.astype('f4').tobytes())

    def vertex_array(self, program):
        return self.ctx.vertex_array(program, [(self.vbo, "3f 3f 3f 2f", "in_vertex", "in_normal", "in_color", "in_uv")])  

    def has_items(self):
        return self.vbo

        
class Chunk:
    SCALE = 100

    def __init__(self, program, position):
        #print("Creating chunk", position)
        # Metadata
        self.program = program
        self.position = position
        self.transform = glm.translate(glm.mat4(1.0), (position[0]*16, position[1]*16, position[2]*16))
        
        # Data
        self.blocks = []

        # Rendering
        self.geometry = None
        self.mesh = None

        for i in range(16):
            w = []
            for j in range(16):
                t = []
                for k in range(16):
                    t.append(None)
                w.append(t)
            self.blocks.append(w)
        self.generate()


    def generate(self):
        #print("Generating chunk", self.position)
        for i in range(16):
            for j in range(16):
                height = noise.pnoise2((self.position[0]*16+i)/Chunk.SCALE, (self.position[1]*16+j)/Chunk.SCALE, octaves=8) * 64 + 64
                for k in range(16):
                    if self.position[2]*16+k < height: 
                        self.blocks[i][j][k] = Cube(self.program, glm.translate(glm.mat4(1.0), (i, j, k)), (0.0, 0.5, random.random()), Blocks.GRASS_BLOCK)
                    else:
                        break

    def create_mesh(self):
        self.geometry = ChunkGeometry(self.blocks)
        if self.geometry.has_items():
            self.mesh = Mesh(self.program, self.geometry, texture=ChunkGeometry.TEXTURE).change_me(self.transform)

    def render(self):
        if self.mesh:
            self.mesh.render()


class Scene:
    SENSITIVITY = 6
    SPEED = 10

    def __init__(self):
        # world info
        self.chunks = {}
        self.time = 0

        self.ctx = moderngl.get_context()

        # player info
        self.pos = glm.vec3(0.0, 0.0, 64.0)
        self.looking = glm.vec4(1.0, 0.0, 0.0, 0.0)

        self.program = self.ctx.program(
            vertex_shader='''
                #version 460 core

                uniform mat4 camera;
                uniform mat4 transform;

                layout (location = 0) in vec3 in_vertex;
                layout (location = 1) in vec3 in_normal;
                layout (location = 2) in vec3 in_color;
                layout (location = 3) in vec2 in_uv;

                out vec4 v_vertex;
                out vec3 v_normal;
                out vec3 v_color;
                out vec2 texCoord;

                void main() {
                    v_vertex = transform * vec4(in_vertex, 1.0);
                    v_normal = in_normal;
                    v_color = in_color;
                    texCoord = in_uv;

                    gl_Position = camera * v_vertex;
                }
            ''',
            fragment_shader='''
                #version 460 core

                uniform sampler2D Texture;
                uniform vec3 lightSource;
                uniform float amb;

                in vec4 v_vertex;
                in vec3 v_normal;
                in vec3 v_color;
                in vec2 texCoord;

                layout (location = 0) out vec4 out_color;

                void main() {
                    vec3 light_d = normalize(lightSource - vec3(v_vertex));
                    float dif = max(0, dot(normalize(v_normal), light_d));

                    float light = amb + dif;

                    vec4 texture_col = texture(Texture, texCoord);
                    if (texture_col.a < 0.01) {
                        discard;
                    }
                    out_color = vec4(light * (vec3(texture_col) * v_color), texture_col.a);
                }
            ''',
        )

    def camera_matrix(self):
        #now = pygame.time.get_ticks() / 1000.0
        proj = glm.perspective(math.radians(60.0), 1.0, 0.1, 1000.0)
        look = glm.lookAt(self.pos, self.pos + glm.vec3(self.looking), (0.0, 0.0, 1.0))
        return proj * look

    def render(self):
        camera = self.camera_matrix()

        self.ctx.clear()
        self.ctx.enable(self.ctx.DEPTH_TEST)

        # Update sun position / camera pos
        light_pos = glm.vec3(0, 0, 70)
        self.program['lightSource'] = light_pos
        self.program['amb'] = 0.5
        self.program['camera'].write(camera)
        
        for chunk in self.chunks.values():
            chunk.render()

    def gen_chunks(self):
        eye = self.pos
        eye_chunk = (int(eye[0]/16), int(eye[1]/16), int(eye[2]/16))
        for i in range(eye_chunk[0] - 1, eye_chunk[0] + 1):
            for j in range(eye_chunk[1] - 1, eye_chunk[1] + 1):
                for k in range(eye_chunk[2] - 1, eye_chunk[2] + 1):
                    req_chunk = (i, j, k)
                    if req_chunk not in self.chunks:
                        my_chunk = Chunk(self.program, (i, j, k))
                        my_chunk.create_mesh()
                        self.chunks[req_chunk] = my_chunk


# Setup
scene = Scene()
clock = pygame.Clock()
pygame.event.set_grab(True)
pygame.mouse.set_visible(False)

while True:    
    dt = clock.tick(120)/1000

    #pygame.mouse.set_pos(0, 0)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.MOUSEMOTION:
            scene.looking = glm.rotate(scene.looking, dt*(math.pi*-event.rel[0]/180)*Scene.SENSITIVITY, (0, 0, 1))
            
            flat_view = glm.vec3(scene.looking)
            flat_view[2] = 0
            axis = glm.cross(flat_view, (0, 0, 1))
            scene.looking = glm.rotate(scene.looking, dt*(math.pi*-event.rel[1]/180)*Scene.SENSITIVITY, axis)

    keys = pygame.key.get_pressed()
    velocity = glm.vec3(0.0)
    to_go = glm.vec3(scene.looking)
    to_go[2] = 0
    if keys[pygame.K_w]:
        velocity += glm.normalize(to_go)    
    if keys[pygame.K_a]:
        velocity -= glm.normalize(glm.cross(to_go, (0, 0, 1)))
    if keys[pygame.K_s]:
        velocity -= glm.normalize(to_go)    
    if keys[pygame.K_d]:
        velocity += glm.normalize(glm.cross(to_go, (0, 0, 1)))
    if keys[pygame.K_SPACE]:
        scene.pos[2] += dt * Scene.SPEED
    if keys[pygame.K_LCTRL]:
        scene.pos[2] -=  dt * Scene.SPEED
    scene.pos += velocity * dt * Scene.SPEED

    scene.time += dt
    scene.gen_chunks()
    scene.render()

    pygame.display.flip()