from __future__ import division
from PAM.components import Component, Property
import numpy, pylab, time, scipy.sparse
import PAM.PAMlib as PAMlib


class Body(Component):
    """ A component used to model blunt bodies. """

    def __init__(self, nx=1, ny=1, nz=1, bottom=2):
        """ Initialization method
        nx: integer
            Number of surfaces in x direction
        ny: integer
            Number of surfaces in y direction
        nz: integer
            Number of surfaces in z direction
        bottom: integer
            Bottom face of the body
            0: open, C0
            1: open, C1
            2: closed
        """ 

        super(Body,self).__init__() 

        self.ms = []
        self.ms.append(numpy.zeros(nx,int))
        self.ms.append(numpy.zeros(ny,int))
        self.ms.append(numpy.zeros(nz,int))

        self.addFace(-2, 3,-0.5)
        self.addFace(-2,-3, 0.5)
        self.addFace( 2, 1,-0.5)
        self.addFace( 3, 1, 0.5)
        self.addFace(-2, 1, 0.5)
        if bottom==2:
            self.addFace(-3, 1,-0.5)

        self.bottom = bottom
        self.ax1 = 1
        self.ax2 = 2

    def setDOFs(self):
        setC1 = self.setC1
        setCornerC1 = self.setCornerC1
        for f in range(len(self.Ks)):
            self.setC1('surf', f, val=True)
        if self.bottom==0:
            setC1('surf', 0, i=-1, u=-1, val=False)
            setC1('edge', 0, i=-1, u=-1, val=True)
            setC1('surf', 1, i=-1, u=-1, val=False)
            setC1('edge', 1, i=-1, u=-1, val=True)
            setC1('surf', 2, i= 0, u= 0, val=False)
            setC1('edge', 2, i= 0, u= 0, val=True)
            setC1('surf', 4, i=-1, u=-1, val=False)
            setC1('edge', 4, i=-1, u=-1, val=True)

    def initializeVariables(self):
        nx = self.Qs[2].shape[1]
        ny = self.Qs[2].shape[0]
        nz = self.Qs[3].shape[0]
        zeros = numpy.zeros
        ones = numpy.ones
        self.variables = {
            'coneL':0.1*ones(2),
            'offset':zeros(3),
            'radii':ones((nx,3),order='F'),
            'pos':zeros((nx,3),order='F'),
            'rot':zeros((nx,3),order='F'),
            'shapeR':zeros((ny,nx),order='F'),
            'shapeT':zeros((nz,nx),order='F'),
            'shapeL':zeros((ny,nx),order='F'),
            'shapeB':zeros((nz,nx),order='F'),
            'shapeF':zeros((ny,nz),order='F'),
            'shapeA':zeros((ny,nz),order='F')
            }
        self.parameters = {
            'nor':ones((nx,3),order='F'),
            'fillet':zeros((nx,4))
            }
        self.setSections()

    def setSections(self, sections=[], t1U=0, t2U=0, t1L=0, t2L=0):
        Ns = self.Ns
        v = self.variables
        p = self.parameters
        for j in range(Ns[2].shape[1]):
            for i in range(Ns[2].shape[0]):
                val = Ns[2][i,j,3]
                if not val == -1:
                    break
            found = False
            for k in range(len(sections)):
                found = found or (val==sections[k])
            if found or sections==[]:
                p['fillet'][j,0] = t1U
                p['fillet'][j,1] = t2U
                p['fillet'][j,2] = t1L
                p['fillet'][j,3] = t2L

    def computeQs(self):
        r = numpy.zeros(3)
        nx = self.Qs[2].shape[1]
        ny = self.Qs[2].shape[0]
        nz = self.Qs[3].shape[0]
        v = self.variables
        p = self.parameters
        b = self.bottom==2
        ax1 = self.ax1
        ax2 = self.ax2

        v['pos'][0] = 2*v['pos'][1] - v['pos'][2]
        v['pos'][-1] = 2*v['pos'][-2] - v['pos'][-3]

        rot0, Da, Di, Dj = PAMlib.computerotations(ax1, ax2, nx, 9*(nx*3-2), v['pos'], p['nor'])
        drot0_dpos = scipy.sparse.csc_matrix((Da,(Di,Dj)),shape=(nx*3,nx*3))
        rot = v['rot']*numpy.pi/180.0 + rot0
        shapes = range(6)
        shapes[2] = PAMlib.computeshape(ny, nx, (4+b)/4.0, 3/4.0, v['radii'], p['fillet'], v['shapeR'])
        shapes[3] = PAMlib.computeshape(nz, nx, 3/4.0, 1/4.0, v['radii'], p['fillet'], v['shapeT'])
        shapes[4] = PAMlib.computeshape(ny, nx, 1/4.0, (-b)/4.0, v['radii'], p['fillet'], v['shapeL'])
        shapes[5] = PAMlib.computeshape(nz, nx, 7/4.0, 5/4.0, v['radii'], p['fillet'], v['shapeB'])
        chord = numpy.ones(nx)

        if self.bottom==2:
            nQ = nx*(4+6*ny+6*nz)
        else:
            nQ = nx*(4+6*ny+3*nz)
        self.dQs_dv = range(len(self.Qs))

        counter = 0
        for f in range(2,len(self.Qs)):
            ni, nj = self.Qs[f].shape[:2]
            self.Qs[f][:,:,:], Da, Di, Dj = PAMlib.computesections(ax1, ax2, -1, ni, nj, ni*nj*21, counter, r, v['offset'], chord, v['pos'], rot, shapes[f])
            self.dQs_dv[f] = scipy.sparse.csc_matrix((Da,(Di,Dj)),shape=(3*ni*nj,nQ))
            counter += 3*ni*nj

        if self.bottom==2:
            nu = int(numpy.ceil(ny/2.0))
            nv = int(numpy.ceil(nz/2.0))
        else:
            nu = ny
            nv = int(numpy.ceil(nz/2.0))

        r = numpy.array([0.0,0.0,0.0])
        self.dQ_dL = range(2)
        self.dQ_drot = range(2)

        dx = numpy.linalg.norm(v['pos'][2,:]-v['pos'][1,:])
        Q = PAMlib.computecone1(True, self.bottom==2, nu, nv, nz, ny, -v['coneL'][0], dx, shapes[2][:,1:3,:], shapes[3][:,1:3,:], shapes[4][:,1:3,:], shapes[5][:,1:3,:], v['shapeF'])
        QtdQ = PAMlib.computecone1(True, self.bottom==2, nu, nv, nz, ny, -v['coneL'][0]-1, dx, shapes[2][:,1:3,:], shapes[3][:,1:3,:], shapes[4][:,1:3,:], shapes[5][:,1:3,:], v['shapeF'])
        self.Qs[0][:,:,:], self.dQ_drot[0] = PAMlib.computecone2(ax1, ax2, ny, nz, 3*ny*nz, r, v['offset'], v['pos'][1,:], rot[1,:], Q)
        self.dQ_dL[0] = PAMlib.computecone2(ax1, ax2, ny, nz, 3*ny*nz, r, v['offset'], v['pos'][1,:], rot[1,:], QtdQ)[0] - self.Qs[0][:,:,:]

        dx = numpy.linalg.norm(v['pos'][-3,:]-v['pos'][-2,:])
        Q = PAMlib.computecone1(False, self.bottom==2, nu, nv, nz, ny, v['coneL'][1], dx, shapes[2][:,-2:-4:-1,:], shapes[3][:,-2:-4:-1,:], shapes[4][:,-2:-4:-1,:], shapes[5][:,-2:-4:-1,:], v['shapeA'])
        QtdQ = PAMlib.computecone1(False, self.bottom==2, nu, nv, nz, ny, v['coneL'][1]+1, dx, shapes[2][:,-2:-4:-1,:], shapes[3][:,-2:-4:-1,:], shapes[4][:,-2:-4:-1,:], shapes[5][:,-2:-4:-1,:], v['shapeA'])
        self.Qs[1][:,:,:], self.dQ_drot[1] = PAMlib.computecone2(ax1, ax2, ny, nz, 3*ny*nz, r, v['offset'], v['pos'][-2,:], rot[-2,:], Q)
        self.dQ_dL[1] = PAMlib.computecone2(ax1, ax2, ny, nz, 3*ny*nz, r, v['offset'], v['pos'][-2,:], rot[-2,:], QtdQ)[0] -  self.Qs[1][:,:,:]

    def setDerivatives(self, var, ind):
        nx = self.Qs[2].shape[1]
        ny = self.Qs[2].shape[0]
        nz = self.Qs[3].shape[0]
        if var=='offset':
            for f in range(len(self.Qs)):
                self.Qs[f][:,:,ind] += 1.0
        elif var=='coneL':
            self.Qs[ind][:,:,:] += self.dQ_dL[ind]
        elif var=='radii':
            p = 0
        elif var=='pos':
            p = 0
        elif var=='rot':
            j = ind[0]
            k = ind[1]
            for f in range(2,len(self.Qs)):
                ni, nj = self.Qs[f].shape[:2]
                self.Qs[f][:,:,:] += PAMlib.inflatevector(ni, nj, 3*ni*nj, self.dQs_dv[f].getcol(nj+nj*k+j).todense()*numpy.pi/180.0)
            if j==1:
                self.Qs[0][:,:,:] += self.dQ_drot[0][:,:,:,k]*numpy.pi/180.0
            elif j==nx-2:
                self.Qs[1][:,:,:] += self.dQ_drot[1][:,:,:,k]*numpy.pi/180.0
        elif var=='shapeR':
            p = 0
        elif var=='shapeT':
            p = 0
        elif var=='shapeL':
            p = 0
        elif var=='shapeB':
            p = 0
        elif var=='shapeF':
            p = 0
        elif var=='shapeA':
            p = 0


if __name__ == '__main__':
    b = Body(nx=8,ny=4,nz=4,bottom=0)
    import PUBS
    from mayavi import mlab
    b.oml0 = PUBS.PUBS(b.Ps)
    b.setDOFs()
    b.oml0.updateBsplines()
    b.computems()
    b.initializeDOFmappings()
    b.initializeVariables()
    b.variables['pos'][:,0] = numpy.linspace(0,4,b.Qs[2].shape[1])
    #b.variables['pos'][:,1] = numpy.linspace(0,4,b.Qs[2].shape[1])
    b.variables['pos'][:,2] = numpy.linspace(0,4,b.Qs[2].shape[1])
    b.variables['pos'][4,1] = -0.5
    #b.variables['shapeL'][:,:] = 0.5
    #b.variables['shapeR'][:,:] = 0.5
    b.parameters['fillet'][:,0] = 0.5
    b.parameters['fillet'][:,1] = 0.5
    b.variables['noseL'] = 0.5
    b.variables['tailL'] = 0.5
    #b.variables['shapeR'][:10,3:-3] = -0.5
    #b.variables['shapeL'][-10:,3:-3] = -0.5
    b.propagateQs()
    b.updateQs()
    b.oml0.computePoints()
    b.oml0.plot()
    name='body'
    b.oml0.write2Tec(name)
