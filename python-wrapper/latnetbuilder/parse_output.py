import re
import math
import numpy as np

class LatNet:
    def __init__(self, size, self_type, gen=None):
        self.size = size
        self.gen = gen
        self.self_type = self_type
    def _getDim(self):
        return len(self.gen.gen_vector)
    def __str__(self):
        if self.gen is not None:
            return '{}({}, {})'.format(self.self_type, self.size, self.gen)
        else:
            return '{}({})'.format(self.self_type, self.size)
    def __repr__(self):
        return str(self)

class GenParam:
    def __init__(self, s, search_type):
        if search_type == 'ordinary':
            self.gen_vector = [int(x) for x in s.split(',')]
        elif search_type == 'polynomial':
            self.gen_vector = [[int(y) for y in x.strip('[ ,]').split(' ')] for x in s.split(',')]
        elif 'digital' in search_type:
            self.gen_vector = s
    def __str__(self):
        return str(self.gen_vector)
    def __repr__(self):
        return str(self)

class SizeParam:
    def __init__(self, s, search_type):
        if search_type in ['ordinary', 'digital-sobol'] or 'digital-explicit' in search_type:
            # try:
            p = s.split('^')
            if len(p) == 2:
                self._set_embedded(int(p[0]), int(p[1]))
            else:
                self._set_simple(int(s))
            # except:
            #     if type(s) == tuple and len(s) == 2:
            #         self._set_embedded(int(s[0]), int(s[1]))
            #     else:
            #         self._set_simple(int(s))

        elif 'polynomial' in search_type:
            p = s.split('^')
            if len(p) == 2:
                self.base = [int(y) for y in p[0].strip('[]').split(' ')]
                self.power = int(p[1])
                self.width = (len(self.base)-1)*self.power
            else:
                self.base = [int(y) for y in s.strip('[]').split(' ')]
                self.power = 1
                self.width = len(self.base)-1
            self.nb_points = 2**self.width

    def _set_embedded(self, base, power):
        self.base = base
        self.power = power
        self.nb_points = self.base**self.power

    def _set_simple(self, points):
        self.nb_points = points
        self.base = self.nb_points
        self.power = 1

    def __str__(self):
        if self.power == 1:
            return str(self.nb_points)
        else:
            return '{}^{}'.format(self.base, self.power)

    def __repr__(self):
        return str(self)


class Result:
    def __init__(self, latnetbuilder=None, seconds=None, search_type=None, matrices=None, merit=None):
        self.latnetbuilder = latnetbuilder
        self.seconds = seconds
        self.search_type = search_type
        self.matrices = matrices
        self.merit = merit
    def __str__(self):
        return '{} : {} ({} s)'.format(self.latnetbuilder, self.merit, self.seconds)
    def __repr__(self):
        return str(self)

    def getDim(self):
        if self.latnetbuilder is None:
            return 0
        elif self.latnetbuilder.gen is not None:
            return self.latnetbuilder._getDim()
        else:
            return len(self.matrices)

    def getMaxLevel(self):
        return int(math.log2(self.latnetbuilder.size.nb_points))

    def matrix(self, coord):
        return self.matrices[coord]

    def getNet(self, coord, level=None):
        if self.latnetbuilder is None:
            return np.array([])
        if level is None:
            nb_points = self.latnetbuilder.size.nb_points
        else:
            nb_points = 2**level
        assert coord < self.getDim()

        if self.search_type == 'ordinary':
            return np.array([self.latnetbuilder.gen.gen_vector[coord]*i/nb_points % 1 for i in range(nb_points)])

        else:
            points = []
            matrice = self.matrix(coord)
            width = matrice.shape[0]
            if level is None:
                level = width
            for x in range(nb_points):
                binary_repr = np.array([((x>>i)&1) for i in range(width)])
                prod = np.mod(matrice.dot(binary_repr), 2)
                points.append(float(sum([prod[i] << (level-1-i) for i in range(level)]))/nb_points)
            return points



def parse_output(console_output, file_output, result_obj, search_type):
    # print(search_type)

    if search_type == 'ordinary':
        pat_latdef = re.compile(r'^BEST LATTICE:\s*lattice\((?P<size>[^,]*),\s*\[(?P<gen>[^\]]*)\]\s*\)\s*:\s*(?P<merit>.*)')
    elif search_type == 'polynomial':
        pat_latdef = re.compile(r'^BEST LATTICE:\s*PolynomialLattice\((?P<size>[^,]*),\s*\[(?P<gen>[^\)]*)\]\s*\)\s*:\s*(?P<merit>.*)')
    
    pat_time = re.compile(r'^ELAPSED CPU TIME:\s*(?P<seconds>\S*)\s*seconds') 
    # seconds = None  
    for line in console_output.split('\n'):
        match = pat_time.match(line)
        if match:
            seconds = float(match.group('seconds'))
            continue

    if search_type in ['ordinary', 'polynomial']:
        for line in console_output.split('\n'):
            match = pat_latdef.match(line)
            if match:
                size = SizeParam(match.group('size'), search_type)
                gen = GenParam(match.group('gen'), search_type)
                merit = float(match.group('merit'))
                latnetbuilder = LatNet(size, self_type='lattice', gen=gen)
                continue

    matrices = []
    if search_type == 'polynomial' or 'digital' in search_type:
        afterOldMatrix = False
        for line in file_output.split('\n'):
            if '//dim' in line:
                M = []
                afterOldMatrix = True
                continue
            try:
                if line == '' and afterOldMatrix:
                    matrices.append(np.array(M))
                    afterOldMatrix = False
                    continue
                if afterOldMatrix:
                    M.append(np.array([int(x) for x in line.split(' ')[:-1]]))
                    continue

            except Exception as e:
                # print(e)
                pass
                
    # print(matrices)

    if search_type == 'digital-sobol':
        direction_numbers = []
        lines = console_output.split('\n')
        for k in range(len(lines)):
            if 'Direction numbers' in lines[k]:
                i = 1
                while ')' not in lines[k+i]:
                    direction_numbers.append([int(x) for x in lines[k+i].strip(' \t\n').split(' ')])
                    i += 1
        for k in range(len(lines)-1, -1, -1):
            if 'merit:' in lines[k]:
                merit = float(lines[k].split(':')[1].strip(' \n'))
                break
        gen = GenParam(direction_numbers, search_type)
        size = SizeParam(str(2**len(matrices[0])), search_type)
        latnetbuilder = LatNet(size, self_type='net', gen=gen)

    if 'digital-polynomial' in search_type:
        lines = console_output.split('\n')
        for k in range(len(lines)):
            if 'Modulus' in lines[k]:
                size = SizeParam(lines[k+1].strip(' '), search_type)
            elif 'GeneratingVector' in lines[k]:
                gen = []
                for i in range(len(matrices)):
                    gen.append([int(x) for x in lines[k+i+1].strip(' \n\t').split(' ')])
        for k in range(len(lines)-1, -1, -1): 
            if 'merit:' in lines[k]:
                merit = float(lines[k].split(':')[1].strip(' \n'))
                break
        
        latnetbuilder = LatNet(size, self_type='net', gen=GenParam(gen, search_type))

    if 'digital-explicit' in search_type:
        lines = console_output.split('\n')
        size = SizeParam('2^' + str(len(matrices[0])), search_type)
        latnetbuilder = LatNet(size, self_type='net')
        for k in range(len(lines)-1, -1, -1):
            if 'merit:' in lines[k]:
                merit = float(lines[k].split(':')[1].strip(' \n'))
                break
        

    result_obj.latnetbuilder = latnetbuilder
    result_obj.merit = merit
    result_obj.seconds = seconds
    result_obj.search_type = search_type
    result_obj.matrices = matrices
