import math
import sys
import glm
import moderngl
import concurrent.futures 
import threading
import pygame
import time
from util.my_chunk import Chunk, ChunkGeometry
import os
os.environ['SDL_WINDOWS_DPI_AWARENESS'] = 'permonitorv2'


class Scene:
    SENSITIVITY = 6

    def __init__(self, program):
        self.ctx = moderngl.get_context()
        self.program = program

    def camera_matrix(self, pos, look):
        #now = pygame.time.get_ticks() / 1000.0
        proj = glm.perspective(math.radians(60.0), 1.0, 0.1, 1000.0)
        look = glm.lookAt(pos, pos + glm.vec3(look), (0.0, 0.0, 1.0))
        return proj * look

    def render(self, chunks, eye, look):
        camera = self.camera_matrix(eye, look)

        self.ctx.clear(0.6, 0.65, 0.8)
        self.ctx.enable(self.ctx.DEPTH_TEST)

        # Update sun position / camera pos
        light_pos = glm.vec3(0, 0, 1024)
        self.program['lightSource'] = light_pos
        self.program['amb'] = 0.3
        self.program['camera'].write(camera)

        eye_chunk = (int(eye[0]/16), int(eye[1]/16), int(eye[2]/16))
        can_mesh_chunk = True
        for i in range(eye_chunk[0] - 5, eye_chunk[0] + 5):
            for j in range(eye_chunk[1] - 5, eye_chunk[1] + 5):
                for k in range(eye_chunk[2] - 5, eye_chunk[2] + 5):
                    req_chunk = (i, j, k)
                    if req_chunk in chunks:
                        chunk = chunks[req_chunk]
                        if can_mesh_chunk:
                            s = chunk.update_mesh_st_safe()
                            if s:
                                can_mesh_chunk = False
                        chunk.render()

        #tv = time.perf_counter_ns() - v
        #if tv > 1000000:
            #print(Chunk.vb_total/Chunk.samples_vb, Chunk.mesh_total/Chunk.samples_vb, Chunk.samples_vb, Chunk.samples_mesh, "Chunk:VB, Chunk:MESH, VB Count, Samples Count")
        


class ServerWorld:
    SPEED = 10

    def __init__(self, program):
        self.program = program

        # pooling
        self.thread = None
        self.chunk_thread_pool = concurrent.futures.ThreadPoolExecutor()
        self.queued_chunks = {}
        
        # world info
        self.chunks = {}
        self.time = 0

        # player info
        self.pos = glm.vec3(0.0, 0.0, 64.0)
        self.looking = glm.vec4(1.0, 0.0, 0.0, 0.0)

    def create_or_load_chunk(self, location):
        my_chunk = Chunk(self.program, location)
        self.chunks[location] = my_chunk

    def _logic_loop(self):
        while True:
            self.gen_chunks()
            time.sleep(0.02)

    def start(self):
        self.thread = threading.Thread(target=self._logic_loop)
        self.thread.start()

    def gen_chunks(self):
        #c = time.perf_counter_ns()
        eye = self.pos
        eye_chunk = (int(eye[0]/16), int(eye[1]/16), int(eye[2]/16))
        for i in range(eye_chunk[0] - 5, eye_chunk[0] + 5):
            for j in range(eye_chunk[1] - 5, eye_chunk[1] + 5):
                for k in range(eye_chunk[2] - 5, eye_chunk[2] + 5):
                    req_chunk = (i, j, k)
                    if req_chunk not in self.chunks and req_chunk not in self.queued_chunks:
                        #print(len(self.chunks), "We need to create chunk ", req_chunk)
                        #self.create_or_load_chunk(req_chunk)
                        future_chunk = self.chunk_thread_pool.submit(self.create_or_load_chunk, req_chunk)
                        #future_chunk.add_done_callback(self.test)
                        self.queued_chunks[req_chunk] = future_chunk
                        return
                        #self.create_or_load_chunk(req_chunk)
        #print(time.perf_counter_ns() - c, "Gen-chunks time")


# Setup
if __name__ == '__main__':
    pygame.init()
    pygame.display.set_mode((800, 800), flags=pygame.OPENGL | pygame.DOUBLEBUF, vsync=True)
    # Called AFTER pygame init
    ChunkGeometry.setup()

    # Program
    context = moderngl.get_context()
    program = context.program(
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

    scene = Scene(program)
    server = ServerWorld(program)
    clock = pygame.Clock()
    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)

    # SERVER SHENANIGANS (MULTI_THREADABLE)
    server.start()

    while True:    
        dt = clock.tick(120)/1000

        # CLIENT SHENANIGANS
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEMOTION:
                server.looking = glm.rotate(server.looking, dt*(math.pi*-event.rel[0]/180)*Scene.SENSITIVITY, (0, 0, 1))
                
                flat_view = glm.vec3(server.looking)
                flat_view[2] = 0
                axis = glm.cross(flat_view, (0, 0, 1))
                server.looking = glm.rotate(server.looking, dt*(math.pi*-event.rel[1]/180)*Scene.SENSITIVITY, axis)

        keys = pygame.key.get_pressed()
        velocity = glm.vec3(0.0)
        to_go = glm.vec3(server.looking)
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
            server.pos[2] += dt * ServerWorld.SPEED
        if keys[pygame.K_LCTRL]:
            server.pos[2] -=  dt * ServerWorld.SPEED
        server.pos += velocity * dt * ServerWorld.SPEED
        server.time += dt

        #print(Chunk.total_gen / Chunk.samples, Chunk.total_geo / Chunk.samples, "Chunk:Gen, Chunk:Geo")
        scene.render(server.chunks, server.pos, server.looking)

        pygame.display.flip()
        #print("Tick done!", dt)
        #exit()