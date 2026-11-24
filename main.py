from util.my_chunk import Chunk, ChunkGeometry
import math
import os
import sys
import glm
import moderngl
import pygame
import concurrent.futures 
import threading

os.environ['SDL_WINDOWS_DPI_AWARENESS'] = 'permonitorv2'

pygame.init()
pygame.display.set_mode((800, 800), flags=pygame.OPENGL | pygame.DOUBLEBUF, vsync=True)
# Called AFTER pygame init
ChunkGeometry.setup()

class Scene:
    SENSITIVITY = 6
    SPEED = 10

    def __init__(self):
        # pooling
        #self.chunk_thread_pool = concurrent.futures.ThreadPoolExecutor()

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
                    float dif = clamp(dot(normalize(v_normal), light_d), 0.1, 1.0);

                    float light = clamp(dif + amb, 0.1, 1.0);

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

        self.ctx.clear(0.6, 0.65, 0.8)
        self.ctx.enable(self.ctx.DEPTH_TEST)

        # Update sun position / camera pos
        light_pos = glm.vec3(0, 0, 1024)
        self.program['lightSource'] = light_pos
        self.program['amb'] = 0.3
        self.program['camera'].write(camera)

        eye = self.pos
        eye_chunk = (int(eye[0]/16), int(eye[1]/16), int(eye[2]/16))
        for i in range(eye_chunk[0] - 5, eye_chunk[0] + 5):
            for j in range(eye_chunk[1] - 5, eye_chunk[1] + 5):
                for k in range(eye_chunk[2] - 5, eye_chunk[2] + 5):
                    req_chunk = (i, j, k)
                    if req_chunk in self.chunks:
                        chunk = self.chunks[req_chunk]
                        chunk.render()

    def create_or_load_chunk(self, location):
        my_chunk = Chunk(self.program, location)
        my_chunk.create_mesh()
        self.chunks[location] = my_chunk

    def gen_chunks(self):
        eye = self.pos
        eye_chunk = (int(eye[0]/16), int(eye[1]/16), int(eye[2]/16))
        for i in range(eye_chunk[0] - 5, eye_chunk[0] + 5):
            for j in range(eye_chunk[1] - 5, eye_chunk[1] + 5):
                for k in range(eye_chunk[2] - 5, eye_chunk[2] + 5):
                    req_chunk = (i, j, k)
                    if req_chunk not in self.chunks:
                        #new_buffer = self.ctx.buffer(reserve=6488064)
                        #new_va = self.ctx.vertex_array(self.program, [(new_buffer, "3f 3f 3f 2f", "in_vertex", "in_normal", "in_color", "in_uv")])
                        self.create_or_load_chunk(req_chunk)
                        #t = threading.Thread(target=self.create_or_load_chunk, args=(req_chunk, new_buffer))
                        #t.start()
                        #print("Queued geneeration of chunk", req_chunk)
                        #self.chunk_thread_pool.submit(self.create_or_load_chunk, req_chunk, new_buffer)
                        


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
    #print(scene.chunks)
    scene.render()

    pygame.display.flip()