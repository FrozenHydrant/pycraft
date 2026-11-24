class Cube:
    def __init__(self, program, transform, color, type):
        #Cube.PLANE_GEOMETRY = PlaneGeometry()
        self.transform = transform
        self.color = color
        self.meshes = []
        self.program = program
        self.type = type