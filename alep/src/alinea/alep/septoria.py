""" Classes of dispersal unit, lesion and ring specific of wheat septoria.

"""
# Imports #########################################################################
from alinea.alep.cycle2 import *
from random import random, randint
from math import floor, ceil
import numpy as np

# Dispersal unit ##################################################################
class SeptoriaDU(DispersalUnit):
    """ Define a dispersal unit specific of septoria.
    
    """
    fungus = None
    def __init__(self, position=None, nb_spores=None, status=None):
        """ Initialize the dispersal unit of septoria.
        
        Parameters
        ----------
        position: non defined
            Position of the dispersal unit on the phyto-element
        nb_spores: int
            Number of spores aggregated in the dispersal unit
        status: str
            'emitted' or 'deposited'
        
        Returns
        -------
            None
        """
        super(SeptoriaDU, self).__init__(position=position, nb_spores=nb_spores, status=status)
        self.cumul_wetness = 0.
            
    def infect(self, dt, leaf, **kwds):
        """ Compute infection by the dispersal unit of Septoria.
        
        Parameters
        ----------
        dt: int
            Time step of the simulation (in hours)
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)

        Returns
        -------
            None
        """
        leaf_wet = leaf.wetness # (boolean): True if the leaf sector is wet during this time step.
        temp = leaf.temp # (float) : mean temperature on the leaf sector during the time step (in degree).
        healthy_surface = leaf.healthy_surface # (float) : healthy surface (=with no lesion) on the leaf sector during the time step (in cm^2).
        try:
            senescence = leaf.position_senescence
        except:
            senescence = None
        
        if healthy_surface > 0. :
            # TODO : Right way to do this ?
            if self.nb_spores == 0.:
                self.disable()
                
            elif senescence and self.position[0] >= senescence:
                self.disable()
           
            else:
                if self.status == 'deposited':
                    # TODO: design a new equation : see Magarey (2005)
                    if leaf_wet:
                        self.cumul_wetness += 1
                    elif self.cumul_wetness > 0: 
                        assert not leaf_wet
                        self.cumul_wetness = 0.
                        # TODO : find a way to reduce inoculum if wet then dry. 
                        # Following lines are a hack - NO biological meaning
                        if proba(self.fungus.loss_rate):
                            self.disable()
                    else:
                        assert not leaf_wet
                        assert self.cumul_wetness == 0.
                    
                    if (self.fungus.temp_min <= temp <= self.fungus.temp_max) and self.cumul_wetness >= self.fungus.wd_min :
                        # TODO : create a function of the number of spores            
                        spores_factor = self.nb_spores / self.nb_spores # always equals 1 for now
                        if proba(spores_factor):
                            self.create_lesion(leaf)
                    elif self.cumul_wetness == 0 :
                        # TODO : Proba conditionnelle doit se cumuler.
                        if proba(self.fungus.loss_rate): 
                            self.disable()
        else:
            self.disable()

# Lesion ##########################################################################
class ContinuousSeptoria(Lesion):
    """ Septoria Lesion implemented as a continuous model. """

    def __init__(self, nb_spores=None, position=None):
        """ Initialize the lesion of septoria. 
        
        Parameters
        ----------
        position: non defined
            Position of the dispersal unit on the phyto-element
        nb_spores: int
            Number of spores aggregated in the dispersal unit
        
        """
        super(ContinuousSeptoria, self).__init__(nb_spores=nb_spores, position=position)
        # Status of the lesion
        self.status = self.fungus.INCUBATING
        # Surface alive of the lesion
        self.surface_alive = 0.
        # Surfaces in each state
        self.surface_inc = 0.
        self.surface_chlo = 0.
        self.surface_nec = 0.
        self.surface_spo = 0.
        # Surface sporulating the time step before
        self.surface_spo_before = 0.
        # Age of the center of the lesion (degree days)
        self.age_dday = 0.
        # Delta age for each time step
        self.ddday = 0.
        # Position of senescence
        self.position_senescence = None
        # Speed of senescence
        self.speed_senescence = None
        # Surface killed by senescence
        self.surface_dead = 0.
        # Growth activity of the lesion
        self.growth_is_active = True
        # Growth rate as a function of lesion status (cm2/degree days)
        self.current_growth_rate = 0.        
        # Growth demand of the lesion (cm2)
        self.growth_demand = 0.
        # Stock of spores (number of spores)
        self.stock = 0.
        # Is first hour of rain
        self.first_rain_hour = False
        # List of DUs emitted
        self.emissions = []

    def update(self, dt=1., leaf=None):
        """ Update the status, age and growth demand of the lesion.

        Parameters
        ----------
        dt: int
            Time step of the simulation (in hours)
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)
        """
        f = self.fungus

        # Disable the lesion if all is sporulating and stock is empty
        if (self.age_dday > 0. and
            self.surface_spo != 0. and
            self.surface_spo == self.surface_alive and
            self.stock == 0.):
            self.disable()
            return
        
        # Compute delta degree days in dt
        # TODO : modify if list of temp coming from weather data
        # self.compute_delta_ddays(dt, leaf)
        self.compute_delta_ddays_from_weather(leaf)
        ddday = self.ddday

        # Update the age of the lesion
        self.age_dday += ddday
        
        # Update the status of the lesion
        self.update_status()
        
        # Update the growth variables of the lesion
        if self.growth_is_active:
            # Update growth rate
            self.update_growth_rate()   
            # Update growth demand
            self.update_growth_demand()
        else:
            self.current_growth_rate = 0.
            self.growth_demand = 0.
        
        # Save senescence position and speed if it is given as MTG property
        self.save_senescence(ddday=ddday, leaf=leaf)

        # Update the perception of rain by the lesion
        if self.status == f.SPORULATING:
            if leaf.rain_intensity > 0. and leaf.relative_humidity >= f.rh_min:
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
            ddday = max(0,(leaf.temp - f.basis_for_dday)/(24./dt))
        else:
            ddday = 0.
        # Save variable
        self.ddday = ddday 
    
    def compute_delta_ddays_from_weather(self, leaf=None):
        """ Compute delta degree days from weather data since last call.
        
        Parameters
        ----------
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions) 
        """
        f = self.fungus
        temp_list = np.array(leaf.temp_list)
        dt = len(temp_list)
        # Calculation
        if dt != 0.:
            ddday = max(0, sum((temp_list - f.basis_for_dday))/24.)
        else:
            ddday = 0.
        # Save variable
        self.ddday = ddday
        
    def update_growth_rate(self):
        """ Update the growth rate of the lesion in cm2/degree days.
        
        Growth rate is low during incubation and faster after this stage.
        If the growth is between the stages, then growth rate is the mean
        between the lower and the faster according to the time spent in each
        stage.
        
        Parameters
        ----------
            None
        """
        f = self.fungus
        ddday = self.ddday
        age_dday = self.age_dday
        time_to_chlo = f.degree_days_to_chlorosis
        
        if age_dday < time_to_chlo: 
            r = f.Smin / time_to_chlo
        elif (age_dday - ddday) < time_to_chlo:
            r1 = f.Smin / time_to_chlo
            r2 = f.growth_rate
            diff1 = time_to_chlo - (age_dday - ddday)
            diff2 = age_dday - time_to_chlo
            r = (diff1*r1 + diff2*r2)/ddday
        else:
            r = f.growth_rate

        self.current_growth_rate = r
    
    def update_status(self):
        """ Update the status of the lesion.
        
        Parameters
        ----------
            None
        """
        status = self.compute_status(age_dday = self.age_dday)
        self.status = status
    
    def compute_status(self, age_dday):
        """ Find the status of a lesion of septoria according to its age in degree days.
        
        Before 220 DD, a lesion of septoria is INCUBATING.
        ______ 330 DD ________________________ CHLOROTIC.
        ______ 350 DD ________________________ NECROTIC.
        After, it is SPORULATING if not EMPTY or DEAD.
        
        Parameters
        ----------
        age_dday: float
            Age of the lesion (degree days)
            
        Returns
        -------
        status: int
            Status of the lesion
        """
        f = self.fungus
        status = [f.SPORULATING, f.INCUBATING, f.CHLOROTIC, f.NECROTIC]
        times = [0,f.degree_days_to_chlorosis, f.degree_days_to_necrosis, f.degree_days_to_sporulation]
        times = np.cumsum(times)
        
        return status[np.argmin(times<=age_dday)] 
        
    def update_growth_demand(self):
        """ Update the growth demand of the lesion according to its current growth rate.
        
        Growth demand is a simple product between growth rate (cm2/degree days) and 
        a delta degree days. 
        
        Parameters
        ----------
            None
        """
        ddday = self.ddday
        r = self.current_growth_rate

        # Compute demand
        demand = r * ddday       
        self.growth_demand = demand
    
    def compute_all_surfaces(self):
        """ Compute all the surfaces in different states of the lesion.
        
        Before chlorosis, a lesion of septoria grows slowly at a rate 'r1'.
        After, it grows at a higher rate 'r2'. 
        
        Parameters
        ----------
            None
        """
        f = self.fungus
        surface_alive = self.surface_alive
        status = self.status
        age_dday = self.age_dday
        r = f.growth_rate
        Smin = f.Smin
        
        time_to_spo = f.degree_days_to_chlorosis + f.degree_days_to_necrosis + f.degree_days_to_sporulation
        time_to_nec = f.degree_days_to_chlorosis + f.degree_days_to_necrosis
        time_to_chlo = f.degree_days_to_chlorosis
        
        # Initiation
        surface_inc = 0.
        surface_chlo = 0.
        surface_nec = 0.
        surface_spo = 0.
        
        # Compute surfaces
        if status == f.INCUBATING:
            surface_inc = surface_alive
            
        elif status == f.CHLOROTIC:
            surface_chlo = surface_alive
            
        elif status == f.NECROTIC:
            delta_age_nec = age_dday - time_to_nec
            # Potential surface in necrosis if no interruption
            pot_surface_nec = Smin + r*delta_age_nec
            if surface_alive < pot_surface_nec:
                # All the lesion is necrotic
                surface_nec = surface_alive
            else:
                # There are necrotic and chlorotic surfaces
                surface_nec = pot_surface_nec
                surface_chlo = surface_alive - surface_nec

        elif status == f.SPORULATING:
            delta_age_spo = age_dday - time_to_spo
            # Potential surface in necrosis if no interruption
            pot_surface_spo = Smin + r*delta_age_spo
            if surface_alive < pot_surface_spo:
                # All the lesion is necrotic
                surface_spo = surface_alive
            else:
                # There are at least sporulating and necrotic surfaces
                surface_spo = pot_surface_spo
                # Potential surface in necrosis if no interruption
                pot_surface_nec = r*f.degree_days_to_necrosis
                if (surface_alive - surface_spo) < pot_surface_nec:
                    # All the rest is necrotic
                    surface_nec = surface_alive - surface_spo
                else:
                    # There are at sporulating, necrotic and chlorotic surfaces
                    surface_nec = pot_surface_nec
                    surface_chlo = surface_alive - surface_spo - surface_nec
        
        # Save variables
        self.surface_inc = surface_inc
        self.surface_chlo = surface_chlo
        self.surface_nec = surface_nec
        self.surface_spo = surface_spo
    
    def compute_sporulating_surface(self):
        """ Compute only the sporulating surface.
        
        Parameters
        ----------
            None
        """
        f = self.fungus
        surface_alive = self.surface_alive
        status = self.status
        age_dday = self.age_dday
        r = f.growth_rate
        Smin = f.Smin
        time_to_spo = f.degree_days_to_chlorosis + f.degree_days_to_necrosis + f.degree_days_to_sporulation
        
        # Initiation
        surface_spo = 0.
        
        if self.status == f.SPORULATING:
            delta_age_spo = age_dday - time_to_spo
            # Potential surface in necrosis if no interruption
            pot_surface_spo = Smin + r*delta_age_spo
            if surface_alive < pot_surface_spo:
                # All the lesion is necrotic
                surface_spo = surface_alive
            else:
                # There are at least sporulating and necrotic surfaces
                surface_spo = pot_surface_spo
                
        # Save sporulating surface
        self.surface_spo = surface_spo
    
    def control_growth(self, growth_offer = 0.):
        """ Reduce surface of the lesion up to available surface on leaf.
        
        Parameters
        ----------
        growth_offer: float
            Minimum between 'growth_demand' and the surface available on
            the leaf for the lesion to grow (cm2) 

        """
        f = self.fungus
        time_of_growth = None
        growth_demand = self.growth_demand
        Smax = f.Smax

        # By default, growth offer is added to surface alive
        self.surface_alive += growth_offer
        # surface_alive = self.surface_alive + growth_offer
        
        # Check if any interruption of growth:
        if self.growth_is_active:
            if (self.surface + growth_offer) >= Smax:
                # Interruption of growth because maximal size has been reached
                self.disable_growth()
                # Compute length of growth period during time step
                time_of_growth = self.compute_time_before_Smax()
                # Compute surface alive
                self.surface_alive = Smax
                # surface_alive = Smax
                
            elif growth_offer < growth_demand:
                # Not interrupted because Smax but interrupted because of competition
                self.disable_growth()
                # Surface alive is computed as in the calculation by default
                # surface_alive = self.surface_alive + growth_offer
                # Compute length of growth period during time step
                time_of_growth = self.compute_time_before_compet(growth_offer)
        
            if self.is_senescent():
                # Interruption because of senescence (independent of the two before)
                self.disable_growth()
                # Compute length of growth period during time step
                time_sen = self.compute_time_before_senescence()
                if time_of_growth:
                    time_of_growth = min(time_of_growth, time_sen)
                else:
                    time_of_growth = time_sen
                  
                # Compute senescence response (update surfaces dead and alive):
                self.senescence_response(time_of_growth, time_sen)
                
        # Update the production of spores of the lesion
        if self.status == f.SPORULATING:
            self.update_stock()
            
    def disable_growth(self):
        """ Shut down lesion growth activity (turn it to False)
        
        Parameters
        ----------
            None
        """
        self.growth_is_active = False

    def compute_time_before_Smax(self):
        """ Compute length of growth period before reaching Smax during time step.
        
        Parameters
        ----------
            None
        """
        f = self.fungus
        Smax = f.Smax
        r = f.growth_rate
        surface = self.surface

        diff = Smax - surface
        time_of_growth = diff/r
        
        return time_of_growth
        
    def compute_time_before_compet(self, growth_offer = 0.):
        """ Compute length of growth period before competition during time step.
        
        Parameters
        ----------
        growth_offer: float
            Minimum between 'growth_demand' and the surface available on
            the leaf for the lesion to grow (cm2) 
        """
        f = self.fungus
        age_dday = self.age_dday
        ddday = self.ddday
        time_to_chlo = f.degree_days_to_chlorosis
        r1 = f.Smin / time_to_chlo
        r2 = f.growth_rate

        # Age before last growth
        age_before = age_dday - ddday
        
        if growth_offer == 0.:
            time_of_growth = 0.
        else:
            if age_dday < time_to_chlo: 
                # Competition occured before reaching chlorosis
                # Growth rate has not changed yet and equals r1
                time_of_growth = growth_offer/r1
            elif age_before > time_to_chlo:
                # Growth rate has not changed in the last time step and equals r2
                time_of_growth = growth_offer/r2
            else:
                # Growth rate has changed in the last time step
                time_with_r1 = time_to_chlo - age_before
                time_with_r2 = (growth_offer - r1*time_with_r1)/r2
                time_of_growth = time_with_r1 + time_with_r2
                assert time_of_growth < ddday
        
        return time_of_growth
    
    def save_senescence(self, ddday=0., leaf=None):
        """ Save variables of senescence.
        
        Parameters
        ----------
        ddday: float
            Delta degree days during 'dt'.
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)
        """
        try:
            senescence = leaf.position_senescence
        except:
            # Senescence is not known in MTG properties
            senescence = None
        if senescence:
            if not self.position_senescence:
                # no senescence before --> Position senescence = position leaf edge
                old_pos = 10. # TODO : Modify with real value
            else:
                old_pos = self.position_senescence
            new_pos = leaf.position_senescence
            if ddday != 0.:
                speed = abs(new_pos-old_pos)/ddday if new_pos != 0. else 0.
            else:
                speed = 0.
            self.position_senescence = new_pos
            self.speed_senescence = speed
    
    def is_senescent(self):
        """ Check if the lesion is affected by leaf senescence.
        
        Parameters
        ----------
            None
            
        Returns
        -------
        True or False:
            The lesion is affected or not by senescence
        """       
        if (self.position_senescence and 
            self.position[0] >= self.position_senescence):
            return True
        else:
            return False
            
    def compute_time_before_senescence(self):
        """ Compute length of growth period before senescence during time step.
        
        Parameters
        ----------
            None
        """
        ddday = self.ddday
        speed = self.speed_senescence
        pos_sen = self.position_senescence

        time_of_growth = ddday - (pos_sen-self.position)/speed if speed!=0. else 0.

        return time_of_growth        
    
    def senescence_response(self, time_of_growth, time_sen):
        """ Compute surface alive and surface dead.
        
        Parameters
        ----------
        time_of_growth: float
            Time before the growth was interrupted (degree days)
        time_sen: float
            Time before the growth was interrupted by senescence
        """
        f = self.fungus
        ddday = self.ddday
        age_dday = self.age_dday
        time_to_chlo = f.degree_days_to_chlorosis
        r1 = f.Smin / time_to_chlo
        r2 = f.growth_rate
        Smin = f.Smin
        
        # Find status of the lesion when senescence occured
        age_sen = age_dday - ddday + time_sen
        status = self.compute_status(age_dday = age_sen)
        
        # Compute surface alive at this time
        age_growth = age_dday - ddday + time_of_growth
        if age_growth < time_to_chlo:
            self.surface_alive = age_growth*r1
        else:
            diff = age_growth - time_to_chlo
            self.surface_alive = f.Smin + diff*r2
        
        # Kill all surfaces under necrosis at this time
        if status <= f.CHLOROTIC:
            self.disable()
            surface_dead = self.surface_alive
        else:
            self.compute_all_surfaces()
            surface_dead = self.surface_chlo
            # temp
            assert self.surface_alive - surface_dead == self.surface_nec + self.surface_spo # temp
        
        # Update 'surface_alive' and 'surface_dead'
        self.surface_alive -= surface_dead if self.surface_alive > 0. else 0.
        self.surface_dead = surface_dead

    def update_stock(self):
        """ Update the stock of spores produced by the lesion.
        
        Each time a new surface is sporulating, it produces a given
        amount of spores by unit of surface : parameter 'production_rate'.
        
        Parameters
        ----------
        None        
        """
        f = self.fungus
        
        # Compute sporulating surface
        self.compute_sporulating_surface()
        
        surface_spo_before = self.surface_spo_before
        surface_spo = self.surface_spo
        
        # Inputs of the stock
        delta_surface_spo = max(0, surface_spo - surface_spo_before)
        self.stock += delta_surface_spo * f.production_rate
        
        # Save 'surface_spo_before' for next time step
        self.surface_spo_before = surface_spo

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
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)
       
        Returns
        -------
        True or False :
            Availability of the stock
        
        """
        f = self.fungus
        
        if (self.stock and self.status == f.SPORULATING and 
            leaf.relative_humidity >= f.rh_min and
            self.first_rain_hour):
            return True
        else:
            return False
    
    def emission(self, leaf = None):
        """ Create a list of dispersal units emitted by the ring.
        
        Parameters
        ----------
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)
        
        .. Todo:: Implement a real formalism.
        """
        if self.is_stock_available(leaf):
            f = self.fungus
            emissions = []
            stock_available = int(self.stock*2/3.)
            
            # TODO : improve below
            nb_DU_emitted = int(leaf.rain_intensity * self.surface_spo * 1000)
            nb_spores_by_DU = []
            for DU in range(nb_DU_emitted):
                if stock_available > 0.:
                    nb_spores = min(randint(5,100), stock_available)
                    nb_spores_by_DU.append(nb_spores)
                    stock_available -= nb_spores
                    # Update stock
                    self.stock -= nb_spores
            
            # Get rid of DUs without spores
            nb_DU_emitted = len(nb_spores_by_DU)
            
            # Empty stock
            if self.stock < 1000:
                self.stock = 0.

            # Return emissions
            emissions = [SeptoriaDU(nb_spores = nb_spores_by_DU[i], status='emitted')
                                    for i in range(nb_DU_emitted)]
                                    
            return emissions
        else:
            return []
            
    @property
    def surface(self):
        """ Compute the surface of the lesion.
        
        Parameters
        ----------
            None
            
        Returns
        -------
        surface: float
            Surface of the lesion
        """
        return self.surface_alive + self.surface_dead

# Septoria with rings #############################################################
class SeptoriaWithRings(Lesion):
    """ Define a lesion specific of septoria with growth rings.
    """
    def __init__(self, nb_spores=None, position=None):
        """ Initialize the lesion of septoria. 
        
        Parameters
        ----------
        position: non defined
            Position of the dispersal unit on the phyto-element
        nb_spores: int
            Number of spores aggregated in the dispersal unit

        """
        super(SeptoriaWithRings, self).__init__(nb_spores=nb_spores, position=position)
        # List of rings, add a ring at lesion formation
        self.rings = []
        ring = SeptoriaRing(lesion = self, status = self.fungus.INCUBATING)
        self.rings.append(ring)
        # Age of the center of the lesion (degree days)
        self.age_dday = 0.
        # Delta degree days during time step
        self.ddday = 0.
        # Position of senescence
        self.position_senescence = None
        # Speed of senescence
        self.speed_senescence = None        
        # Surface of disabled rings
        self.surface_dead = 0.
        # Growth activity of the lesion
        self.growth_is_active = True
        # Growth demand of the lesion (cm2)
        self._growth_demand = None
        # Is first hour of rain
        self.first_rain_hour = False
    
    def update(self, dt, leaf, **kwds):
        """ Update the status of the lesion and create a new growth ring if needed.
                
        Parameters
        ----------
        dt: int
            Time step of the simulation (in hours)
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)

        """
        assert self.is_active
        f = self.fungus
        
        # Compute delta degree days in dt
        # TODO : modify if list of temp coming from weather data
        # self.compute_delta_ddays(dt, leaf)
        self.compute_delta_ddays_from_weather(leaf)
        ddday = self.ddday
        
        # Save senescence position and speed if it is given as MTG property
        self.save_senescence(ddday=ddday, leaf=leaf)
        
        if self.is_senescent():           
            # Compute ddday to stop lesion development at time of senescence
            ddday -= self.compute_dday_since_senescence()

        # Update the age of the lesion
        self.age_dday += ddday
            
        # Ageing of the rings / create new ones when needed
        nb_rings_initial = len(self.rings)
        # Note that new rings can be added in this time step, 
        # their update is managed by another module
        for i in range(nb_rings_initial):
        # for ring in self.rings:
            self.rings[i].update(ddday=ddday, lesion=self)
        
        # Update the perception of rain by the lesion
        if self.status == f.SPORULATING:
            if leaf.rain_intensity > 0. and leaf.relative_humidity >= f.rh_min:
                self.first_rain_hour = True if not self.first_rain_hour else False
            else:
                self.first_rain_hour = False

    def save_senescence(self, ddday=0., leaf=None):
        """ Save variables of senescence.
        
        Parameters
        ----------
        ddday: float
            Delta degree days during 'dt'.
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)
        """
        try:
            senescence = leaf.position_senescence
        except:
            # Senescence is not known in MTG properties
            senescence = None
        if senescence:
            if not self.position_senescence:
                # no senescence before --> Position senescence = position leaf edge
                old_pos = 10. # TODO : Modify with real value
            else:
                old_pos = self.position_senescence
            new_pos = leaf.position_senescence
            if ddday != 0.:
                speed = abs(new_pos-old_pos)/ddday if new_pos != 0. else 0.
            else:
                speed = 0.
            self.position_senescence = new_pos
            self.speed_senescence = speed
        
    def add_rings(self, list_of_rings=None):
        """ Add rings to list of rings if needed.
        
        Parameters
        ----------
        list_of_rings: list of ring instantiations
            Rings of lesion with properties (e.g. surface, status, age, etc.)       
        """
        self.rings += list_of_rings
    
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
            ddday = max(0,(leaf.temp - f.basis_for_dday)/(24./dt))
        else:
            ddday = 0.
        # Save variable
        self.ddday = ddday 

    def compute_delta_ddays_from_weather(self, leaf=None):
        """ Compute delta degree days from weather data since last call.
        
        Parameters
        ----------
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions) 
        """
        f = self.fungus
        temp_list = np.array(leaf.temp_list)
        dt = len(temp_list)
        # Calculation
        if dt != 0.:
            ddday = max(0, sum((temp_list - f.basis_for_dday))/(24./dt))
        else:
            ddday = 0.
        # Save variable
        self.ddday = ddday
     
    def control_growth(self, growth_offer = 0.):
        """ Reduce surface of the last ring up to available surface on leaf.
        
        Parameters
        ----------
        growth_offer: float
            Surface available on the leaf for the ring to grow (cm2)
        """
        f = self.fungus
        total_growth_demand = self.growth_demand
        growth_offer_left = min(growth_offer, f.Smax - self.surface)

        rings_in_formation = [r for r in self.rings if r.is_in_formation(fungus=f)]
        if rings_in_formation:
            for ring in rings_in_formation:
                ring_growth_offer = min(ring.growth_demand, growth_offer_left)
                growth_offer_left -= ring.growth_demand if growth_offer_left>0. else 0.
                ring.control_growth(ring_growth_offer, lesion=self)
        
        # Update stock
        new_rings_sporulating = [r for r in self.rings if (r.is_sporulating(fungus=f) and r.stock==None)]
        # Note: at initiation, stock=-1. It is only filled once.
        # The aim is to avoid refilling it when it falls back to 0.
        if new_rings_sporulating:
            for ring in new_rings_sporulating:
                ring.update_stock(lesion=self)
        
        # Disable growth when needed
        if growth_offer < total_growth_demand or self.surface == f.Smax:
            self.disable_growth()
        
        if self.is_senescent():
            self.disable_growth()
            # Response to senescence
            self.senescence_response()
                        
        # Remove non active rings
        self.surface_dead += sum(ring.surface for ring in self.rings if not ring.is_active)
        self.rings = [ring for ring in self.rings if ring.is_active]

        # Disable lesion when no ring left
        if not self.rings:
            self.disable()
            return
        
    def is_senescent(self):
        """ Check if the lesion is affected by leaf senescence.
        
        Parameters
        ----------
            None
            
        Returns
        -------
        True or False:
            The lesion is affected or not by senescence
        """       
        if (self.position_senescence and 
            self.position[0] >= self.position_senescence):
            return True
        else:
            return False
        
    def compute_dday_since_senescence(self):
        """ Compute delta degree days after senescence during time step.
        
        Parameters
        ----------
            None
        """
        speed = self.speed_senescence
        pos_sen = self.position_senescence
        dday_since_senescence = (pos_sen-self.position)/speed if speed!=0. else 0.
        return dday_since_senescence  
    
    def senescence_response(self, time_since_sen=0.):
        """ Kill rings affected by senescence and achieve ageing of the other rings
            up to the end of time step.
        
        During the time step, the growth of the lesion has been stopped when 
        senescence occured. Now, at the end of time step, we can suppress all
        the rings that do not survive senescence, and complete the ageing of the 
        others.
        
        Parameters
        ----------
        time_since_sen: float
            Time since growth interruption (degree days)
        """
        f = self.fungus
        
        dday_since_senescence = self.compute_dday_since_senescence()
        self.age_dday += dday_since_senescence
        
        for ring in self.rings:
            if ring.status < f.NECROTIC:
                # Disable all rings under NECROTIC state:
                ring.disable()
            else:
                # To be sure, reset all useless ring variables
                # Then update them to make them reach the end of time step
                ring.growth_demand = 0.
                ring.delta_growth = 0.
                ring.delta_age_left = None
                ring.growth_is_active = False
                ring.update(ddday=dday_since_senescence, lesion=self)
    
    def emission(self, leaf, **kwds):
        """ Create a list of dispersal units emitted by the entire lesion.
        
        Parameters
        ----------
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)
        
        Returns
        -------
        emissions: 
        """
        emissions = []
        for ring in self.rings:
           if ring.is_stock_available(lesion = self):
                ring_emissions = ring.emission(leaf, lesion=self)
                if ring_emissions:
                    emissions += ring_emissions
        
        return emissions    
        
    def disable_growth(self):
        """ Shut down lesion growth activity (turn it to False)
        
        Parameters
        ----------
            None
        """
        self.growth_is_active = False
    
    def is_dead(self):
        """ Update the status of all the rings to 'DEAD' if the lesion is dead.
        
        Parameters
        ----------
            None
        """
        return all(ring.is_dead() for ring in self.rings)
        
    def compute_all_surfaces(self):
        """ Compute lesion surfaces in different states.
        
        Parameters
        ----------
            None
            
        ..NOTE:: Temporary just for tests
        """
        f = self.fungus
        self.surface_inc = sum(r.surface for r in self.rings if r.is_incubating(f))
        self.surface_chlo = sum(r.surface for r in self.rings if r.is_chlorotic(f))
        self.surface_nec = sum(r.surface for r in self.rings if r.is_necrotic(f))
        self.surface_spo = sum(r.surface for r in self.rings if r.is_sporulating(f))
      
    @property
    def surface_alive(self):
        """ Compute the surface alive on the lesion.
        
        Parameters
        ----------
            None
            
        ..NOTE:: Temporary just for tests
        """
        return sum(ring.surface for ring in self.rings)
  
    @property
    def surface(self):
        """ Compute the surface of the lesion.
        
        Parameters
        ----------
            None
            
        Returns
        -------
        surface: float
            Surface of the whole lesion (cm2)
        """
        surf = self.surface_dead + sum(ring.surface for ring in self.rings)
        return surf
    
    @property
    def growth_demand(self):
        """ Compute the growth_demand of the lesion.
        
        If a single ring is in formation, growth demand of the lesion equals growth 
        demand of this ring. If a new ring is emerging at this time step, two rings
        are in formation.        
        
        Parameters
        ----------
            None
            
        Returns
        -------
        surface: float
            Surface of the whole lesion (cm2)
        """
        fungus = self.fungus
        
        if self.rings:
            forming_rings = [r for r in self.rings if r.is_in_formation(fungus)]
            self._growth_demand = sum(r.growth_demand for r in forming_rings)
        else:
            self._growth_demand = 0.
        return self._growth_demand
    
    @property
    def stock(self):
        """ Compute the stock of spores on the lesion.
        
        Parameters
        ----------
            None
            
        Returns
        -------
        surface: float
            Surface of the whole lesion (cm2)
        """
        stock = sum(ring.stock for ring in self.rings if ring.stock >0.)
        return stock
    
    @property
    def status(self):
        """ Compute the status of the lesion.
        
        Parameters
        ----------
            None
            
        Returns
        -------
        status: int
            Status of the lesion
        """
        if self.rings:
            return self.rings[0].status
            
    # @property
    # def age_dday(self):
        # """ Compute the thermal age of the lesion.
        
        # Parameters
        # ----------
            # None
            
        # Returns
        # -------
        # age_dday: float
            # Age of the lesion in degree days
        # """
        # if self.rings:
            # return self.rings[0].age_dday

    @status.setter
    def status(self, value):
        """ Set the status of the lesion to the chosen value.
        
        Parameters
        ----------
        value : int
            Chosen value to set lesion status
            
        Returns
        -------
            None
        """
        if self.rings:
            self.rings[0].status = value
            
    @growth_demand.setter
    def growth_demand(self, value):
        """ Set the growth demand of the lesion to the chosen value.
        
        Parameters
        ----------
        value : int
            Chosen value to set lesion status
            
        Returns
        -------
            None
        """
        self._growth_demand = value
        
# Rings ###########################################################################
class SeptoriaRing(Ring):
    """ Ring of Lesion of Septoria at a given age.
    """
    def __init__(self, lesion, status):
        """ Initialize each new ring of septoria. 
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
        status : int
            Status of the ring when initiated
            
        Returns
        -------
            None 
        """
        super(SeptoriaRing, self).__init__()
        f = lesion.fungus        
        # Status of the ring
        self.status = status
        # Surface of the ring
        self.surface = 0.
        # Age of the ring
        self.age_dday = 0.
        # Delta degree days of growth during time step
        # self.ddday = 0.
        self.delta_growth = 0.
        # Delta age to complete the ring
        if len(lesion.rings)==0.:
            self.delta_age_left = f.degree_days_to_chlorosis + f.delta_age_left
        else:
            self.delta_age_left = f.delta_age_left
        # Activity of the ring
        self.is_active = True
        # Growth activity of the ring
        self.growth_is_active = True
        
        # See later for dispersion
        self.cumul_rain_event = 0.
        self.rain_before = False
        self.stock = None

    def is_in_formation(self, fungus):
        """ Can keep growing!!! """
        ok = self.growth_is_active
        return ok

    def is_incubating(self, fungus):
        return self.status == fungus.INCUBATING

    def is_chlorotic(self, fungus):
        return self.status == fungus.CHLOROTIC

    def is_necrotic(self, fungus):
        return self.status == fungus.NECROTIC

    def is_sporulating(self, fungus):
        return self.status == fungus.SPORULATING

    def is_empty(self, fungus):
        return self.status == fungus.EMPTY

    def is_dead(self, fungus):
        return self.status == fungus.DEAD

    def update(self, ddday, lesion=None):
        """ Update the status of the ring.
        
        * Cumulate the age of the ring.
        * Assign leaf data to the ring in order to access it in the methods.
        * Call the property 'stage' depending on the current status of the ring.
        
        Parameters
        ----------
        ddday: float
            Delta degree days during 'dt'
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)            
        """
        f = lesion.fungus
                
        # Ageing of the ring
        self.age_dday += ddday
        if not self.is_in_formation(fungus=f):
            # Compute status of the ring
            self.stage(lesion=lesion)
        else:
            # Create new rings if needed
            if ddday > self.delta_age_left:
                self.create_new_rings(ddday=(ddday - self.delta_age_left), lesion=lesion)
                # Update delta age of growth
                self.delta_growth = self.delta_age_left
                # Reset delta_age_left
                self.delta_age_left = None
            else:
                # Update delta age of growth
                self.delta_growth = ddday
                # Update delta age left until growth completion
                self.delta_age_left -= ddday
            
            # Compute status of the ring
            self.stage(lesion=lesion)
                
    def create_new_rings(self, ddday=0., lesion=None):
        """ Add rings to lesion list of rings if needed.
        
        Parameters
        ----------
        ddday: float
            Delta degree days in 'dt' since apparition of new rings
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)   
        """
        f = lesion.fungus
        list_of_rings = []

        # Creation of the first new ring
        new_ring = SeptoriaRing(lesion=lesion, status=f.CHLOROTIC)
        list_of_rings.append(new_ring)
        list_of_rings[-1].age_dday = ddday 
        list_of_rings[-1].delta_growth = min(ddday, list_of_rings[-1].delta_age_left)
        
        # Creation of the following rings with properties ('age_dday', 'delta_growth', 'delta_age_left')
        while list_of_rings[-1].age_dday > list_of_rings[-1].delta_age_left:
            ddday -= list_of_rings[-1].delta_age_left
            list_of_rings[-1].delta_age_left = None
            new_ring = SeptoriaRing(lesion=lesion, status=f.CHLOROTIC)
            list_of_rings.append(new_ring)
            list_of_rings[-1].age_dday = ddday
            list_of_rings[-1].delta_growth = min(ddday, list_of_rings[-1].delta_age_left)
            
        list_of_rings[-1].delta_age_left -= list_of_rings[-1].age_dday
        
        # Status of new rings
        for ring in list_of_rings:
            # ring.delta_age_left -= ring.age_dday 
            ring.stage(lesion=lesion)
        
        # Attach each new ring to the lesion
        lesion.add_rings(list_of_rings)
            
    def in_formation(self, lesion=None, **kwds):
        """ Compute growth demand according to delta age of growth during time step.        
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
            
        Returns
        -------
            None
        """     
        f = lesion.fungus
        delta_growth = self.delta_growth
       
        if self.is_incubating(fungus=f):
            # First ring in incubation
            self.growth_demand = f.Smin * delta_growth / f.degree_days_to_chlorosis
        else:
            # All the other rings
            self.growth_demand = delta_growth * f.growth_rate

    def control_growth(self, growth_offer = 0., lesion=None):
        """ Reduce surface of the rings in formation down to available surface on leaf.
        
        Parameters
        ----------
        growth_offer: float
            Minimum between the surface available on the leaf for the ring
            to grow (cm2) and 'growth_demand'
        """
        f = lesion.fungus

        # Add surface
        self.surface += growth_offer

        if self.surface==0. and growth_offer == 0.:
            # Turn off the ring
            self.disable()
        elif self.delta_age_left == None:
            # Turn off growth activity if no delta age left before growth completion
            self.disable_growth()

        # Update stock for sporulating rings
        # if self.is_sporulating(fungus=f):
            # self.update_stock(lesion=lesion)
        
    def incubating(self, lesion=None, **kwds):
        """ Set the status of the ring to CHLOROTIC when needed.
        
        Only the first ring can be incubating. It must wait 220DD to become CHLOROTIC
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
        """
        f = lesion.fungus
        time_to_chlorosis = f.degree_days_to_chlorosis
        assert self.is_incubating(fungus=f)
        
        # Compute status transition to necrotic
        if self.age_dday >= time_to_chlorosis:
            self.status = f.CHLOROTIC
            self.chlorotic(lesion=lesion)
    
    def chlorotic(self, lesion=None, **kwds):
        """ Set the status of the ring to NECROTIC when needed.
        
        Each ring entering in the CHLOROTIC stage must wait 110 DD 
        to be NECROTIC.
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
        """
        f = lesion.fungus
        if lesion.surface_dead==0. and self == lesion.rings[0]:
            time_to_necrosis = f.degree_days_to_chlorosis + f.degree_days_to_necrosis
        else:
            time_to_necrosis = f.degree_days_to_necrosis
        assert self.is_chlorotic(fungus=f)

        # Compute status transition to necrotic
        if self.age_dday >= time_to_necrosis:
            self.status = f.NECROTIC
            self.necrotic(lesion=lesion)
            
    def necrotic(self, lesion=None, **kwds):
        """ Set the status of the ring to SPORULATING when needed.
        
        Each ring entering in the CHLOROTIC stage must wait ??? DD 
        to be SPORULATING.
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
        """
        f = lesion.fungus
        if lesion.surface_dead==0. and self == lesion.rings[0]:
            time_to_spo = (f.degree_days_to_chlorosis + 
                           f.degree_days_to_necrosis + 
                           f.degree_days_to_sporulation)
        else:
            time_to_spo = (f.degree_days_to_necrosis + 
                           f.degree_days_to_sporulation)
        assert self.is_necrotic(fungus=f)
        
        # Compute status transition to sporulating
        if self.age_dday >= time_to_spo:
            self.status = f.SPORULATING

    def sporulating(self, lesion=None, **kwds):
        """ Compute the number of rain events on the ring, 
        and update the status of the ring when needed.
        
        A sporulating ring bears fructifications containing dispersal units.
        These dispersal units are spread by the rain if the relative humidity
        is greater than or equal to 85%. It is assumed that the ring is EMPTY
        after 3 separate rain events.
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)

        .. Todo:: Enhance the code to parametrize the code with a function.
        """
        f = lesion.fungus
        assert self.is_sporulating(fungus=f)
        
        # Count dispersal events
        # if lesion.first_rain_hour:
            # self.cumul_rain_event += 1
        
        # Empty the ring after 3 rain events
        # if self.cumul_rain_event >= f.rain_events_to_empty:
            # self.empty(lesion)
            
        self.update_stock(lesion=lesion)
        
    def update_stock(self, lesion=None):
        """ Update the stock of spores on the ring.
        
        Fill the stock of spores according to production rate and surface of the ring.
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
        """
        f = lesion.fungus

        production = self.surface * f.production_rate           
        nb_spores_produced = int(round(production))
        self.stock = nb_spores_produced
        # Note: explains the +1 above :
        # At initiation stock=-1. It is only filled once.
        # The aim is to avoid refilling it when it falls back to 0.

    def emission(self, leaf=None, lesion=None, **kwds):
        """ Create a list of dispersal units emitted by the ring.
        
        Parameters
        ----------
        leaf: Leaf sector node of an MTG 
            A leaf sector with properties (e.g. healthy surface,
            senescence, rain intensity, wetness, temperature, lesions)
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
        
        Returns
        -------
        emissions: list of DUs
            DUs emitted by the ring
        
        .. Todo:: Implement a real formalism.
        """
        f = lesion.fungus
        emissions = []
        stock_available = int(self.stock*2/3.)
        
        # TODO : improve below
        nb_DU_emitted = int(leaf.rain_intensity * self.surface * 1000)
        nb_spores_by_DU = []
        for DU in range(nb_DU_emitted):
            if stock_available > 0.:
                nb_spores = min(randint(5,100), stock_available)
                nb_spores_by_DU.append(nb_spores)
                stock_available -= nb_spores
                # Update stock
                self.stock -= nb_spores
                
        # Get rid of DUs without spores
        nb_DU_emitted = len(nb_spores_by_DU)
        
        # Empty stock
        if self.stock < 100:
            self.empty(lesion)

        # Return emissions
        emissions = [SeptoriaDU(nb_spores = nb_spores_by_DU[i], status='emitted')
                                for i in range(nb_DU_emitted)]
        
        return emissions
           
    def is_stock_available(self, lesion=None):
        """ Check if the stock of DU can be emitted.
        
        DU is free for liberation if :
            - there are DUs in stock_du
            - ring is sporulating
            - relative humidity is above a treshold
            - it is the first hour of rain
            
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
        
        Returns
        -------
        True or False :
            Availability of the stock
        """
        f = lesion.fungus
        
        if (self.stock and self.status == f.SPORULATING and 
            lesion.first_rain_hour):
            return True
        else:
            return False
        
    def empty(self, lesion=None, **kwds):
        """ Disable the 'EMPTY' ring.
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
        """
        f = lesion.fungus
        self.status = f.EMPTY
        self.disable()
        
    def dead(self, lesion=None, **kwds):
        """ Disable the 'DEAD' ring.
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
            
        Returns
        -------
            None
        """
        self.status = lesion.fungus.DEAD
        self.disable()
    
    def disable(self, **kwds):
        """ Set the activity of the ring to 'False'.
        
        Parameters
        ----------
            None
            
        Returns
        -------
            None
        """
        self.is_active = False
        
    def disable_growth(self):
        """ Shut down lesion growth activity (turn it to False).
        
        Parameters
        ----------
            None
        """
        self.growth_is_active = False
        self.growth_demand = 0.
        
    def stage(self, lesion=None):
        """ Orient the ring to toward the proper function according to its status.
        
        Parameters
        ----------
        lesion : Lesion instantiation
            The lesion carrying the ring, with properties 
            (e.g. fungus parameters, surface, status, age, rings, etc.)
            
        Returns
        -------
        None
            Call the method corresponding to ring status  
        """
        f = lesion.fungus
        
        # Cumulation of surface
        if self.is_in_formation(fungus=f):
            self.in_formation(lesion=lesion)
        
        # Ageing
        if self.is_incubating(fungus=f):
            self.incubating(lesion=lesion)
        elif self.is_chlorotic(fungus=f):
            self.chlorotic(lesion=lesion)
        elif self.is_necrotic(fungus=f):
            self.necrotic(lesion=lesion)
        
        # Update stock
        # if self.is_sporulating(fungus=f):
            # NOTE : update stock moved in growth control
            # self.sporulating(lesion=lesion)
        elif self.is_empty(fungus=f):
            self.empty(lesion=lesion)
        elif self.is_dead(fungus=f):
            self.dead(lesion=lesion)

# Fungus parameters (e.g. .ini): config of the fungus #############################
class SeptoriaParameters(Parameters):
    def __init__(self,
                 INCUBATING = 0,
                 CHLOROTIC = 1,
                 NECROTIC = 2,
                 SPORULATING = 3,
                 EMPTY = 4,
                 DEAD = 5,
                 delta_age_left = 20.,
                 basis_for_dday = -2.,
                 temp_min = 10.,
                 temp_max = 30.,
                 wd_min = 10.,
                 loss_rate = 1./120,
                 degree_days_to_chlorosis = 220.,
                 degree_days_to_necrosis = 110.,
                 degree_days_to_sporulation = 20.,
                 epsilon = 0.001,
                 Smin = 0.03,
                 Smax = 0.3,
                 growth_rate = 0.0006,
                 rh_min = 85.,
                 rain_events_to_empty = 3,
                 production_rate = 100000,
                 *args, **kwds):
        """ Parameters for septoria.
        
        Parameters
        ----------
        delta_age_left: int
            Time step in degree days to create a new ring
        basis_for_dday: float
            Basis temperature for the accumulation of degree days (degrees celsius)
        temp_min: float
            Minimal temperature for infection
        temp_max: float
            Maximal temperature for infection
        wd_min: float
            Minimal wetness duration for infection
        loss_rate: float
            Loss rate of dispersal units in 1 hour
        degree_days_to_chlorosis: float
            Thermal time between emergence and chlorosis
            (i.e. incubation for the first rings)
        degree_days_to_necrosis: float
            Thermal time between chlorosis and necrosis
            (i.e. incubation for the first rings)
        degree_days_to_sporulation: float
            Thermal time between necrosis and sporulation
        epsilon: float
            Initial size of incubating lesion (cm2)
        Smin: float
            Initial size of chlorotic lesion (cm2)
        Smax: float
            Lesion maximum size (cm2)
        growth_rate: float
            Lesion growth rate (cm2.dday-1)
        rh_min: float
            Minimal relative humidity for sporulation
        rain_events_to_empty: int
            Number of rain events to empty a sporulating ring
        """
        self.name = "Septoria"
        self.INCUBATING = INCUBATING
        self.CHLOROTIC = CHLOROTIC
        self.NECROTIC = NECROTIC
        self.SPORULATING = SPORULATING
        self.EMPTY = EMPTY
        self.DEAD = DEAD
        self.delta_age_left = delta_age_left
        self.basis_for_dday = basis_for_dday
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.wd_min = wd_min
        self.loss_rate = loss_rate
        self.degree_days_to_chlorosis = degree_days_to_chlorosis
        self.degree_days_to_necrosis = degree_days_to_necrosis
        # TODO : Find value for parameters !!
        self.degree_days_to_sporulation = degree_days_to_sporulation
        self.epsilon = epsilon
        self.Smin = Smin
        self.Smax = Smax
        self.growth_rate = growth_rate
        self.rh_min = rh_min
        self.rain_events_to_empty = rain_events_to_empty
        self.production_rate = production_rate
        # TODO : Improve this parameter. 

    # def __call__(self, nb_spores = None, position = None):
        # if SeptoriaWithRings.fungus is None:
            # SeptoriaWithRings.fungus = self
        # if SeptoriaDU.fungus is None:
            # SeptoriaDU.fungus = self
        # return SeptoriaWithRings(nb_spores=nb_spores, position=position)
        
    def __call__(self, nb_spores = None, position = None):
        if ContinuousSeptoria.fungus is None:
            ContinuousSeptoria.fungus = self
        if SeptoriaDU.fungus is None:
            SeptoriaDU.fungus = self
        return ContinuousSeptoria(nb_spores=nb_spores, position=position)

def septoria(**kwds):
    return SeptoriaParameters(**kwds)

# Useful functions ################################################################
def proba(p):
    """ Compute the occurence of an event according to p.

    Parameters
    ----------
    p : float
        Probability of the event in [0,1]
    
    Returns
    -------
    True or False
    """
    return random() < p
