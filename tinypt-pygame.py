# ======== Imports ========

import random
from math import *
import threading
import time
import sys, os, traceback
import pygame
from pygame.locals import *
from pygame.math import Vector2 as Vec2
from pygame.math import Vector3 as Vec3

# ======== PyGame and Windowing Setup ========

if sys.platform in ["win32","win64"]: os.environ["SDL_VIDEO_CENTERED"]="1"
pygame.display.init()
pygame.font.init()

res = [400,300]
icon = pygame.Surface((1,1)); icon.set_alpha(0); pygame.display.set_icon(icon)
pygame.display.set_caption("SmallPT PyGame - Ian Mallett - 2018")

surface = pygame.display.set_mode(res)

# ======== Misc. Helper Functions ========

def rndint(x): return int(round(x))
def clamp(x, low,high):
    if   x<low:  return low
    elif x>high: return high
    return x

#Returns two additional vectors that are orthogonal to the given vector and to each other.
def get_frame(vec1):
    if abs(vec1[1]) < 0.8:
        vec0 = ( Vec3(0,1,0).cross(vec1) ).normalize()
    else:
        vec0 = ( Vec3(1,0,0).cross(vec1) ).normalize()
    vec2 = vec1.cross(vec0)
    return vec0, vec1, vec2

# ======== Random Sampling Functions ========

#Returns a randomly-generated unit vector on the surface of a sphere.
def random_sphere():
    return Vec3(
        random.gauss(0,1),
        random.gauss(0,1),
        random.gauss(0,1)
    ).normalize()
#Returns a randomly-generated point within the unit disk.
def random_disk():
    sqrtr = random.random() ** 0.5
    theta = 2.0*pi * random.random()
    return sqrtr * Vec2(cos(theta),sin(theta))
#Returns a randomly-generated unit vector on the surface of the hemisphere centered around the given
#   unit vector `normal`.  The values are weighted so that values near this vector are more likely.
def random_coshemisphere(normal):
    disk = random_disk()
    hemi = Vec3(disk[0],clamp(1.0-disk.length_squared(),0.0,1.0)**0.5,disk[1])
    vec0,vec1,vec2 = get_frame(normal)
    return hemi[0]*vec0 + hemi[1]*vec1 + hemi[2]*vec2

# ======== Ray Type ========

class Ray(object):
    def __init__(self, origin,normalized_direction):
        self.origin = origin
        self.normalized_direction = normalized_direction
    def at(self, t):
        return self.origin + t*self.normalized_direction
    def step(self, t):
        self.origin += t * self.normalized_direction

# ======== Object Types ========

class Sphere(object):
    def __init__(self, center,radius, diffuse_constant,emission):
        self.center = center
        self.radius = radius
        self.diffuse_constant = diffuse_constant
        self.emission = emission
    def intersected_by(self, ray):
        delta = ray.origin - self.center
        a = 1.0 #length of ray (normalized)
        b = 2.0 * ray.normalized_direction.dot( delta )
        c = delta.dot(delta) - self.radius*self.radius
        discr = b*b - 4.0*a*c
        if discr <= 0.0:
            return False, None, None
        t = ( -b - discr**0.5 ) / (2.0*a)
        if t <= 0.0:
            return False, None, None
        hit_pos = ray.at(t)
        normal = ( hit_pos - self.center ).normalize()
        return True, t, normal

# ======== Threads ========

class ThreadTrace(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        t0 = time.time()
        
        camera_position = Vec3(0,0.5,0)
        aspect_ratio = float(res[0]) / float(res[1])
        
        objects = [
            Sphere( Vec3(-2,1,-4),1, Vec3(0.6,0.8,0.6),50.0*Vec3(1.0,0.9,0.8) ),

            Sphere( Vec3(0,-10001,-4),10000, Vec3(0.9,0.9,0.9),Vec3(0.0,0.0,0.0) ),
            Sphere( Vec3( 0,0,-3),1, Vec3(0.9,0.6,0.2),Vec3(0.0,0.0,0.0) )
        ]
        
        num_samples = 4
        max_depth = 10

        #For each pixel . . .
        for j in range(res[1]):
            for i in range(res[0]):
                #Estimate the light (`average_radiance`) coming through the pixel by averaging
                #   `num_samples` number of randomly-generated possible light paths.
                
                average_radiance = Vec3(0,0,0) #RGB

                recurse_direction = None

                #To estimate each sample, we:
                for s in range(num_samples):
                    #Generate ray through pixel
                    direction = Vec3(
                        2.0*( (float(i)+random.random())/float(res[0]) ) - 1.0,
                        2.0*( (float(j)+random.random())/float(res[1]) ) - 1.0,
                        -1.0
                    )
                    direction[0] *= aspect_ratio
                    direction.normalize_ip()
                    ray = Ray(camera_position,direction)

                    #Main path tracing loop. Find out how much light is propagating back along this
                    #   ray into the pixel up to a maximum depth `max_depth`.
                    radiance = Vec3(0,0,0)
                    throughput = Vec3(1,1,1)
                    for d in range(max_depth):
                        #Find first object ray hits
                        closest_object         = None
                        closest_distance       = float("inf")
                        closest_surface_normal = None
                        for obj in objects:
                            did_hit, hit_distance, hit_surface_normal = obj.intersected_by(ray)
                            if did_hit:
                                if closest_object==None or hit_distance<closest_distance:
                                    closest_object         = obj
                                    closest_distance       = hit_distance
                                    closest_surface_normal = hit_surface_normal

                        #If we don't hit anything, then the path doesn't hit anything else and we're
                        #   done
                        if closest_object == None:
                            break

                        #Add light emitted by object (zero for most objects), times the fraction
                        #   that makes it back to the pixel.
                        radiance += throughput.elementwise() * closest_object.emission

                        #Replace `ray` with a new ray, loop back, and try again, thus extending the
                        #   light path we're adding light along.
                        throughput = throughput.elementwise() * closest_object.diffuse_constant / pi
                        recurse_origin    = ray.at(closest_distance)
                        recurse_direction = random_coshemisphere(closest_surface_normal)
                        ray = Ray(recurse_origin,recurse_direction)
                        ray.step(0.001) #offset a little bit to reduce numerical problems
                        
                    average_radiance += radiance
                    
                average_radiance /= float(num_samples)

                #Ignore radiometric to colorimetric conversion (and radiance to radiant flux
                #   conversion) and just do the simple thing . . .
                color = pygame.Color(
                    clamp( rndint(average_radiance[0]*255.0), 0,255 ),
                    clamp( rndint(average_radiance[1]*255.0), 0,255 ),
                    clamp( rndint(average_radiance[2]*255.0), 0,255 )
                )
                color.correct_gamma(1.0/2.2) #Also, this is slightly incorrect . . .
                
                surface.set_at( (i,res[1]-j-1), color )

        t1 = time.time()
        pygame.image.save(surface,"rendered-"+str(hash(random.random()))+".png")
        print("Complete (rendered in "+str(t1-t0)+" seconds)!")

class ThreadGUI(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        clock = pygame.time.Clock()
        looping = True
        while looping:
            for event in pygame.event.get():
                if   event.type == QUIT: looping=False
                elif event.type == KEYDOWN:
                    if   event.key == K_ESCAPE: looping=False
            pygame.display.flip()
            clock.tick(60)

# ======== Main ========

def main():
    thread_trace = ThreadTrace()
    thread_gui   = ThreadGUI  ()

    #This doesn't actually work, because SDL (and therefore pygame) has a
    #   limitation that display functions must be called on the main thread.
##    thread_trace.start()
##    thread_gui  .start()
##    thread_trace.join()
##    thread_gui  .join()

    #Run the GUI on the main thread instead.
    thread_trace.start()
    thread_gui.run()
    thread_trace.join()
    
    pygame.quit()
    
if __name__ == "__main__":
    try:
        main()
    except:
        traceback.print_exc()
        pygame.quit()
        input()
