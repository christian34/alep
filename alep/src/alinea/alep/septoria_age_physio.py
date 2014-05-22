""" Class of lesion of wheat septoria. 
    Progress from one state to another is computed with physiological age.
"""

# Imports #########################################################################
from alinea.alep.fungal_objects import *
from alinea.alep.septoria import Disease as _Disease, SeptoriaParameters as _SeptoriaParameters
import numpy as np
from math import floor, ceil

# Lesion ##########################################################################
class SeptoriaAgePhysio(Lesion):
    """ Lesion of septoria implemented with growth stages that exchange surfaces
        according to their physiological age.
    """
    def __init__(self,  nb_spores=None, position=None):
        """ Initialize the lesion of septoria. 
        
        Parameters
        ----------
        nb_spores: int
            Number of spores aggregated in the dispersal unit
        position: non defined
            Position of the dispersal unit on the phyto-element
        """
        super(SeptoriaAgePhysio, self).__init__(nb_spores=nb_spores, position=position)
        # Status of the center of the lesion
        self.status = self.fungus.INCUBATING
        # Age of the center of the lesion
        self.age_dday = 0.
        self.age_physio = 0.
        # Status of the periphery of the lesion
        self.status_edge = self.fungus.INCUBATING
        # Age of the periphery of the lesion
        self.age_physio_edge = 0.
        # Ratio left to progress in new status when center of the lesion changes status during time step
        self.ratio_left = 0.
        self.ratio_left_edge = 0.
        # Surfaces exchanged
        self.to_necrosis = 0.
        self.to_sporulation = 0.
        # Factor for sharing surfaces in new forming rings (number of rings to fill)
        self.distribution_new_rings = 0.
        # Rings in each state
        self.surface_first_ring = 0.
        self.surfaces_chlo = np.array([])
        self.surfaces_nec = np.array([])
        self.surface_spo = 0.
        self.surface_empty = 0.
        # Surface of disabled rings
        self.surface_dead = 0.
        # Stock of spores
        self.stock_spores = None
        self.nb_spores_emitted = 0.
        # Is first hour of rain
        self.first_rain_hour = False
        # Counter of calculation for senescence
        self.can_compute_senescence = True
        # Old position senescence
        self.old_position_senescence = None
        # dt left after senescence
        self.dt_before_senescence = None
        self.dt_left_after_senescence = None
    
        # Temporary
        self.previous_surface = 0.
        self.hist_age = []
        self.hist_inc = []
        self.hist_chlo = []
        self.hist_nec = []
        self.hist_spo = []
        self.hist_empty = []
        self.hist_can_compute_rings = []
        self.hist_nb_rings_chlo = []
    
    def is_incubating(self):
        """ Check if lesion status is incubation. """
        return self.status == self.fungus.INCUBATING
    
    def is_chlorotic(self):
        """ Check if lesion status is chlorosis. """
        return self.status == self.fungus.CHLOROTIC
        
    def is_necrotic(self):
        """ Check if lesion status is necrosis. """
        return self.status == self.fungus.NECROTIC
    
    def is_sporulating(self):
        """ Check if lesion status is sporulation. """
        return self.status == self.fungus.SPORULATING
    
    def update(self, dt, leaf=None):
        """ Update the status of the lesion and create a new growth ring if needed.
                
        Parameters
        ----------
        dt: int
            Time step of the simulation (in hours)
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. area, green area, healthy area,
            senescence, rain intensity, wetness, temperature, lesions, etc.)
        """
        # Manage senescence
        if self.is_senescent and self.can_compute_senescence==True:
            dt = self.compute_time_before_senescence(dt, leaf=leaf)
        self.old_position_senescence = leaf.position_senescence
        
        # Compute delta degree days in dt
        self.compute_delta_ddays(dt, leaf)
        
        if self.ddday > 0.:
            # Update age in degree days of the lesion
            self.age_dday += self.ddday        
            # Update growth demand and status
            self.update_status()
        
        # Temporary
        self.hist_age.append(self.age_dday)
        self.hist_inc.append(self.surface_inc)
        self.hist_chlo.append(self.surface_chlo)
        self.hist_nec.append(self.surface_nec)
        self.hist_spo.append(self.surface_spo)
        self.hist_empty.append(self.surface_empty)
        self.hist_can_compute_rings.append(self.can_compute_rings())
        self.hist_nb_rings_chlo.append(len(self.surfaces_chlo))
        
        # Temporary      
        # if self.surface_chlo>0. and len(self.surfaces_nec>1.) and self.surfaces_nec[0]==0.:
            # import pdb
            # pdb.set_trace()
        
        # Manage rain perception
        if leaf.rain_intensity > 0. and leaf.relative_humidity >= self.fungus.rh_min:
            self.first_rain_hour = True if not self.first_rain_hour else False
        else:
            self.first_rain_hour = False

    def compute_delta_ddays(self, dt=1., leaf=None):
        """ Compute delta degree days in dt.
        
        Parameters
        ----------
        dt: int
            Time step of the simulation (in hours)
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions) 
        """
        f = self.fungus
        # Calculation
        if dt != 0.:
            ddday = max(0,(leaf.temp - f.basis_for_dday*dt)/(24./dt))
        else:
            ddday = 0.
        # Save variable
        self.ddday = ddday
    
    def progress(self, age_threshold=0.):
        """ Compute progress in physiological age according to age_threshold. 
        """
        left = self.ratio_left
        if left==0.:
            # Normal situation
            progress = self.ddday/age_threshold if age_threshold>0. else 0.
        elif left>0.:
            # Passing from one state to another in same time step
            assert left<1.
            progress = left*self.ddday/age_threshold if age_threshold>0. else 0.
            # Reset ratio left and age physio
            self.ratio_left = 0.
        return progress
    
    def control_growth(self, growth_offer=0.):
        """ Reduce surface of the rings up to available surface on leaf.
        
        Parameters
        ----------
        growth_offer: float
            Surface available on the leaf for the ring to grow (cm2)
        """
        if self.growth_is_active:
        
            # TEMPORARY
            if growth_offer<self.growth_demand:
                self.age_competition = self.age_dday
        
            f = self.fungus
            # Growth offer is added to surface according to state
            if self.is_incubating():
                if growth_offer<0:
                    import pdb
                    pdb.set_trace()
                self.surface_first_ring += growth_offer
            else:
                if self.surface_first_ring < f.Smin:
                    if self.surface_first_ring + growth_offer <= f.Smin:
                        self.surface_first_ring += growth_offer
                        growth_offer = 0.
                    else: 
                        self.surface_first_ring = f.Smin
                        growth_offer += self.surface_first_ring - f.Smin
                nb_full_rings = int(floor(self.distribution_new_rings))
                surf = np.array([])
                for rg in range(nb_full_rings):
                    filling = growth_offer/self.distribution_new_rings
                    growth_offer-=filling
                    surf = np.append(surf, filling)
                surf = np.append(surf, growth_offer)
                # Fill surfaces chlo
                if len(surf)<=len(self.surfaces_chlo):
                    self.surfaces_chlo[:len(surf)]+=surf
                else:
                    nb_existing = len(self.surfaces_chlo)
                    nb_to_create = len(surf) - len(self.surfaces_chlo)
                    self.surfaces_chlo += surf[:len(self.surfaces_chlo)]
                    self.surfaces_chlo = np.append(self.surfaces_chlo, surf[len(self.surfaces_chlo):])

            # Reset distribution in new rings and growth demand
            self.distribution_new_ring = 0.         

            # If lesion has reached max size, disable growth
            if self.surface >= f.Smax:
                self.disable_growth()  

            # Disable growth in case of competition 
            if growth_offer < self.growth_demand:
                self.disable_growth()
                
            self.growth_demand = 0.
    
    def incubation(self):
        """ Compute growth demand and physiological age progress to chlorosis.
        """
        f = self.fungus
        time_to_chlo = f.degree_days_to_chlorosis
        # Compute progress in incubation
        progress = self.progress(age_threshold=time_to_chlo)
        self.age_physio += progress
        # Compute growth demand
        if self.age_physio<1.:
            if self.surface_first_ring<0:
                import pdb
                pdb.set_trace()
            if self.growth_is_active:
                self.growth_demand = progress * f.Smin
        else:
            if self.growth_is_active:
                self.growth_demand = f.Smin - self.surface
            # Change status
            self.ratio_left = (self.age_physio - 1.)/progress
            self.change_status()
            self.change_status_edge()
            self.reset_age_physio()
            self.chlorosis()

    def chlorosis(self):
        """ Compute growth demand and physiological age progress to necrosis.
        """       
        f = self.fungus
        # Compute progress in chlorosis
        time_to_nec = f.degree_days_to_necrosis
        progress = self.progress(age_threshold=time_to_nec)
                
        # Compute growth demand
        if self.growth_is_active:
            # Note : '+=' because might be added to growth demand in incubation 
            # if transition in same time step; added to zero otherwise.
            self.growth_demand += progress * time_to_nec * f.growth_rate
            # Limit growth to size max
            if self.surface + self.growth_demand >= f.Smax:
                self.growth_demand = f.Smax - self.surface 
                
        # Compute exchanges of surfaces
        if self.can_compute_rings():
            age_physio = self.age_physio
            age_edge = self.age_physio_edge
            default_nb_rings = f.nb_rings_by_state
            # 'rings' is the division of the stage in classes of age
            # 'width' is the width in physiologic age of each class
            (rings, width) = np.linspace(0,1, default_nb_rings+1, retstep=True)
            # Calculate the number of rings in which chlorosis input will be shared
            self.distribution_new_rings = progress/width
            if self.is_chlorotic() and age_physio==0.:
                pass
                # (No exchange of surface the first time step the lesion enters stage)
            else:
                # Calculate exchanges of surfaces between rings 
                # 1. Reduce the superior limit of ring ages if age_physio in chlorosis
                if self.is_chlorotic():
                    rings = rings[:ceil(age_physio/width)+1]
                    rings[-1] = age_physio
                # 2. Reduce the inferior limit of ring ages if age_edge in chlorosis
                if self.status_edge==f.CHLOROTIC:
                    rings = rings[floor(age_edge/width):]
                    rings[0] = age_edge
                
                # 3. Get the beginnings and the ends of age classes
                begs = rings[:-1]
                ends = rings[1:]
                # 4. Apply progress to the beginnings and the ends of age classes
                begs_prog = begs + progress
                ends_prog = ends + progress
                # 5. Find ends of new classes in which surfaces will be distributed after progress
                new_ends = np.arange(max(0.1, width*ceil(begs_prog[0]/width)), width*(ceil(ends_prog[-1]/width)+1), width)
                new_ends = np.round(new_ends, 14)
                
                # 6. Loop over this classes to calculate the new distribution in each class
                new_surf = np.zeros(len(new_ends))              
                for j in range(len(new_ends)):
                    # Find beginnings and ends of rings in new class
                    ind_begs = np.where((new_ends[j]-width <= begs_prog) * (begs_prog < new_ends[j]))[0]
                    ind_ends = np.where((new_ends[j]-width <= ends_prog) * (ends_prog < new_ends[j]))[0]
                    indexes = np.unique(np.append(ind_begs, ind_ends))
                    # Calculate ratio of old class in new class
                    for ind in indexes:
                        new_surf[j] += round((min(ends_prog[ind], new_ends[j])-
                                              max(begs_prog[ind],new_ends[j]-width))*
                                              self.surfaces_chlo[ind]/(ends[ind]-begs[ind]), 14)
                # 7. Update surfaces and calculate what passes to necrosis
                self.surfaces_chlo = np.extract(new_ends<=1, new_surf)
                self.to_necrosis = sum(np.extract(new_ends>1, new_surf))
                
        # Ageing of the periphery of the lesion if growth has been stopped
        if self.status_edge==f.CHLOROTIC and not self.growth_is_active :
            if self.age_physio_edge+progress < 1.:
                self.age_physio_edge += progress
            else:
                diff = self.age_physio_edge + progress - 1.
                self.ratio_left_edge = diff/progress
                self.change_status_edge()
                self.reset_age_physio_edge()
        
        # Ageing of the center of the lesion
        if self.is_chlorotic():
            if self.age_physio+progress < 1.:
                self.age_physio += progress
            else:
                diff = self.age_physio + progress - 1.
                self.ratio_left = diff/progress
                self.change_status()
                self.reset_age_physio()
                self.necrosis()
        
        # if self.is_necrotic() and self.status_edge==f.CHLOROTIC and self.age_physio_edge==0. and len(self.surfaces_chlo)<=10.:
            # import pdb
            # pdb.set_trace()
    
    def necrosis(self):
        """ Compute physiological age progress to sporulation.
        """
        f = self.fungus
        # Compute progress in necrosis
        time_to_spo = f.degree_days_to_sporulation
        progress = self.progress(age_threshold=time_to_spo)
        
        # Compute exchanges of surfaces
        if self.can_compute_rings():
            age_physio = self.age_physio
            age_edge = self.age_physio_edge
            default_nb_rings = f.nb_rings_by_state
            (rings, width) = np.linspace(0,1, default_nb_rings+1, retstep=True)
            if self.is_necrotic() and age_physio==0.:
                pass
            else:           
                if self.is_necrotic():
                    rings = rings[:ceil(age_physio/width)+1]
                    rings[-1] = self.age_physio
                if self.status_edge==f.NECROTIC:
                    rings = rings[floor(age_edge/width):]
                    rings[0] = self.age_physio_edge
                begs = rings[:-1]
                ends = rings[1:]
                begs_prog = begs + progress
                ends_prog = ends + progress          
                # new_classes = np.arange(width*ceil(begs_prog[0]/width),
                                        # width*(ceil(ends_prog[-1]/width)+1),
                                        # width)
                # new_classes = np.round(new_classes, 14)
                new_ends = np.arange(max(0.1, width*ceil(begs_prog[0]/width)), width*(ceil(ends_prog[-1]/width)+1), width)
                new_ends = np.round(new_ends, 14)
                
                new_surf = np.zeros(len(new_ends))
                for j in range(len(new_ends)):
                    # Find beginnings and ends of rings in class
                    ind_begs = np.where((new_ends[j]-width <= begs_prog) * (begs_prog < new_ends[j]))[0]
                    ind_ends = np.where((new_ends[j]-width <= ends_prog) * (ends_prog < new_ends[j]))[0]
                    indexes = np.unique(np.append(ind_begs, ind_ends))
                    for ind in indexes:
                        new_surf[j] += round((min(ends_prog[ind], new_ends[j])-
                                              max(begs_prog[ind],new_ends[j]-width))*
                                              self.surfaces_nec[ind]/(ends[ind]-begs[ind]), 14)
                                    
                # Pour recuperer ce qui passe dans l'etat suivant
                self.surfaces_nec = np.extract(new_ends<=1, new_surf)
                self.to_sporulation = sum(np.extract(new_ends>1, new_surf))
        
            # Filling of new rings
            nb_full_rings = int(floor(progress/width))
            surf = np.array([])
            for rg in range(nb_full_rings):
                filling = self.to_necrosis*width/progress if progress > 0. else 0.
                self.to_necrosis -= filling
                surf = np.append(surf, filling)
            surf = np.append(surf, self.to_necrosis)
            if len(surf)<=len(self.surfaces_nec):
                self.surfaces_nec[:len(surf)]+=surf
            else:
                nb_existing = len(self.surfaces_nec)
                nb_to_create = len(surf) - len(self.surfaces_nec)
                self.surfaces_nec += surf[:len(self.surfaces_nec)]
                self.surfaces_nec = np.append(self.surfaces_nec, surf[len(self.surfaces_nec):])
            self.to_necrosis = 0.
        
        # Ageing of the periphery of the lesion if growth has been stopped       
        if self.status_edge==f.NECROTIC and not self.growth_is_active:
            if self.age_physio_edge==0. and self.ratio_left_edge>0.:
                self.age_physio_edge += progress*self.ratio_left_edge
                self.ratio_left_edge = 0.
            elif self.age_physio_edge+progress < 1.:
                self.age_physio_edge += progress
            else:
                diff = self.age_physio_edge + progress - 1.
                self.ratio_left_edge = diff/progress
                self.change_status_edge()
    
        # Ageing of the center of the lesion
        if self.is_necrotic():
            if self.age_physio+progress < 1.:
                self.age_physio += progress
            else:
                diff = self.age_physio + progress - 1.
                self.ratio_left = diff/progress
                self.change_status()
                self.reset_age_physio()
                self.sporulation()
     
    def sporulation(self):
        """ Compute production of spores. """
        f = self.fungus
        # First time first ring sporulates
        if self.stock_spores==None:
            self.stock_spores = self.surface_first_ring * f.production_rate
            self.surface_spo += self.surface_first_ring
        self.stock_spores += self.to_sporulation * f.production_rate
        self.surface_spo += self.to_sporulation
        self.to_sporulation = 0.
    
    def is_stock_available(self, leaf):
        """ Check if the stock of DU can be emitted.
        
        DU is free for liberation if :
            - there are DUs in stock_du
            - ring is sporulating
            - relative humidity is above a treshold
            - it is the first hour of rain
            
        Parameters
        ----------
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. area, green area, healthy area,
            senescence, rain intensity, wetness, temperature, lesions)
       
        Returns
        -------
        True or False :
            Availability of the stock
        
        """
        f = self.fungus
        return (self.stock_spores>0. and self.is_sporulating() and 
                leaf.relative_humidity >= f.rh_min and self.first_rain_hour)

    def reduce_stock(self, nb_spores_emitted):
        """ Reduce the stock of spores after emission.
        
        Parameters
        ----------
        nb_spores_emitted: int
            Number of spores emitted
        """
        self.stock_spores -= nb_spores_emitted
        if self.stock_spores < self.fungus.threshold_spores:
            self.stock_spores = 0.
    
    def update_empty_surface(self, nb_spores_emitted, initial_stock):  
        """ Update empty surface after emission. 
        
        In this case, the surface is emptied proportionally  to the number of spores emitted.
        
        Parameters
        ----------
        nb_spores_emitted: int
            Number of spores emitted
        initial_stock: int
            Number of spores on the lesion before emission
        """
        assert initial_stock>0.
        f = self.fungus
        new_surface_empty = (nb_spores_emitted/initial_stock) * self.surface_spo
        self.surface_empty += new_surface_empty
        self.surface_spo = max(0., self.surface_spo-new_surface_empty)
        self.nb_spores_emitted += nb_spores_emitted
        if self.status_edge == f.SPORULATING and self.surface_spo == 0.:
            self.change_status()
            self.disable()
    
    def compute_time_before_senescence(self, dt=1., leaf=None):
        """ Compute portion of time step before senescence. """
        old_pos = self.old_position_senescence
        new_pos = leaf.position_senescence
        speed = (old_pos - new_pos)/dt if dt > 0. else 0.
        new_dt = (old_pos-self.position[0])/speed if speed >0. else 0.
        self.dt_before_senescence = dt
        self.dt_left_after_senescence = dt - new_dt
        return new_dt
    
    def become_senescent(self):
        """ The lesion will become senescent during this time step.
        """
        self.is_senescent = True    
    
    def senescence_response(self):
        """ Compute surface alive and surface dead after senescence. """
        if self.can_compute_senescence:
            self.can_compute_senescence = False
            
            # Stop growth
            self.disable_growth()
        
            # Calculate surface dead according to status
            f = self.fungus
            age_switch = f.age_physio_switch_senescence
            age_physio = self.age_physio
            age_edge = self.age_physio_edge
                        
            if self.status < f.CHLOROTIC:
                self.surface_dead = self.surface_alive
                if self.surface_dead<0.:
                    import pdb
                    pdb.set_trace()
                self.surface_first_ring = 0.
                self.disable()
            elif self.is_chlorotic() and age_switch >= age_physio:
                self.surface_dead = self.surface_alive
                self.surface_first_ring = 0.
                self.surfaces_chlo = np.array([])
                self.disable()
            elif self.status_edge == f.CHLOROTIC and age_switch > age_edge:
                default_nb_rings = f.nb_rings_by_state
                (rings, width) = np.linspace(0,1, default_nb_rings+1, retstep=True)
                if self.is_chlorotic():
                    rings = rings[:ceil(age_physio/width)+1]
                    rings[-1] = age_physio
                rings = rings[floor(age_edge/width):]
                rings[0] = age_edge
                self.surface_dead = sum(np.extract(rings<age_switch-width, self.surfaces_chlo))
                self.surfaces_chlo = self.surfaces_chlo[np.where(rings<age_switch)[0][-1]:]
                self.surface_dead += self.surfaces_chlo[0]*round(age_switch%width, 14)/width
                self.surfaces_chlo[0]*=(1-round(age_switch%width, 14)/width)
                if self.surfaces_chlo[0]==0.:
                    self.surfaces_chlo = self.surfaces_chlo[1:]
                if age_switch==1:
                    self.age_physio_edge = 0.
                    self.change_status_edge()
                else:
                    self.age_physio_edge = age_switch
        
            # Complete the evolution of the lesion up to the end of time step
            if self.is_active:
                self.age_dday += self.dt_left_after_senescence*self.ddday/self.dt_before_senescence
                self.update_status()

    def update_status(self):
        """ Update growth demand and status. """
        # A REORDONNER
        f = self.fungus
        status = self.status
        if status <= f.INCUBATING:
            self.incubation()
        elif status <= f.CHLOROTIC:
            self.chlorosis()
        elif status <= f.NECROTIC:
            if self.status_edge <= f.CHLOROTIC:
                self.chlorosis()
            self.necrosis()
        else:
            if self.status_edge <= f.CHLOROTIC:
                self.chlorosis()
            if self.status_edge <= f.NECROTIC:
                self.necrosis()
            self.sporulation()
        
    def change_status(self):
        """ Passes the status of the center of the lesion from one status to the next. """
        self.status += 1
    
    def change_status_edge(self):
        """ Passes the status of the edge of the lesion from one status to the next. """
        self.status_edge +=1
    
    def reset_age_physio(self):
        """ Turn age physio to 0. """
        self.age_physio = 0.
    
    def reset_age_physio_edge(self):
        """ Turn age physio to 0. """
        self.age_physio_edge = 0.
    
    def can_compute_rings(self):
        """ Allow ring formation only if particular first ring has reached Smin. """
        f = self.fungus
        return round(self.surface_first_ring, 16) == f.Smin

    def compute_all_surfaces(self):
        """ Not needed in this model.
        ..TODO: Remove """
        pass
    
    @property
    def surface_inc(self):
        """ Calculate the surface in incubation. """
        return self.surface_first_ring if self.is_incubating() else 0.

    @property
    def surface_chlo(self):
        """ Calculate the surface in chlorosis. """
        return (sum(self.surfaces_chlo)+self.surface_first_ring) if self.is_chlorotic() else sum(self.surfaces_chlo)

    @property
    def surface_nec(self):
        """ Calculate the surface in chlorosis. """
        return (sum(self.surfaces_nec)+self.surface_first_ring) if self.is_necrotic() else sum(self.surfaces_nec)

    @property
    def necrotic_area(self):
        """ calculate surface necrotic + sporulating. """
        return self.surface_nec + self.surface_spo + self.surface_empty
    
    @property
    def surface_alive(self):
        """ Calculate the surface alive of the lesion. """
        return self.surface_inc + self.surface_chlo + self.surface_nec + self.surface_spo + self.surface_empty
        
    @property
    def surface(self):
        """ Calculate the total surface of the lesion. """
        return self.surface_alive + self.surface_dead

class Parameters(_SeptoriaParameters):
    def __init__(self,**kwds):
        _SeptoriaParameters.__init__(self, model=SeptoriaAgePhysio, **kwds)
        
class Disease(_Disease):
    @classmethod
    def parameters(cls, **kwds):
        return Parameters(**kwds)
    
    @classmethod
    def lesion(cls, **kwds):
        SeptoriaAgePhysio.fungus=cls.parameters(**kwds)
        return SeptoriaAgePhysio