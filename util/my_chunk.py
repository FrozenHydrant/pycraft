from util.extra import Sides, Blocks
from util.uv import TexturesAndUV
from util.texture import SimpleImageTexture
from util.mesh import Mesh
from util.cube import Cube
import moderngl
import numpy as np
import glm
import noise
import random
#import time

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
    TEXTURE = None
    UV_MAPPING = None

    def setup():
        uv_generation = TexturesAndUV()
        ChunkGeometry.TEXTURE = SimpleImageTexture(uv_generation.get_texture_atlas())
        my_uvs = uv_generation.get_uvs()
        ChunkGeometry.UV_MAPPING = {(Sides.PIX, Blocks.GRASS_BLOCK): my_uvs["grass_block_side"],
                        (Sides.SID, Blocks.GRASS_BLOCK): my_uvs["grass_block_side"],
                        (Sides.SKY, Blocks.GRASS_BLOCK): my_uvs["grass_block_side"],
                        (Sides.WOR, Blocks.GRASS_BLOCK): my_uvs["grass_block_side"],
                        (Sides.BOT, Blocks.GRASS_BLOCK): my_uvs["grass_block_top"],
                        (Sides.TOP, Blocks.GRASS_BLOCK): my_uvs["grass_block_top"]}

    def __init__(self):
        self.vbo = None
        self.ctx = moderngl.get_context()
        self.np_vertices = None

    # Updates the vertices of this geometry based on the blocks in the chunk
    def update_vertices(self, blocks):
        temp_vertices = []
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
                                temp_vertices.append(elt)
                            for elt in ChunkGeometry.NORMALS[side]:
                                temp_vertices.append(elt)

                            mix_col = (1, 1, 1)
                            if side == Sides.TOP and c_block.type == Blocks.GRASS_BLOCK:
                                mix_col = (0.3, 0.6, 0.05)
                            for elt in mix_col:
                                temp_vertices.append(elt)

                            # Add UV info
                            for elt in uvs[index]:
                                temp_vertices.append(elt)
                            index += 1

        self.np_vertices = np.array(temp_vertices)

    def update_vbo_st_safe(self):
        if self.np_vertices.shape[0] > 0:
            self.vbo = self.ctx.buffer(self.np_vertices.astype('f4').tobytes())

    def vertex_array(self, program):
        va = self.ctx.vertex_array(program, [(self.vbo, "3f 3f 3f 2f", "in_vertex", "in_normal", "in_color", "in_uv")])  
        return va


        
class Chunk:
    total_gen = 0
    total_geo = 0
    SCALE = 100

    def __init__(self, program, position):
        # Metadata
        self.dirty = 0
        self.program = program
        self.position = position
        self.transform = glm.translate(glm.mat4(1.0), (position[0]*16, position[1]*16, position[2]*16))
        
        # Data
        self.blocks = []

        # Rendering
        self.geometry = ChunkGeometry()
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
        self.update_geometry()


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
        self.dirty = 1

    def update_geometry(self):
        self.geometry.update_vertices(self.blocks)

    def _update_geo_buffers_st_safe(self):
        self.geometry.update_vbo_st_safe()

    def update_mesh_st_safe(self): 
        if self.dirty == 1:
            self._update_geo_buffers_st_safe() 
            if self.geometry.vbo is not None:
                self.mesh = Mesh(self.program, self.geometry, texture=ChunkGeometry.TEXTURE).change_me(self.transform)
        self.dirty = 0

    def render(self):
        if self.mesh:
            self.mesh.render()