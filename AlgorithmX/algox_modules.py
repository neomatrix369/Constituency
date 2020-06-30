# Modules used in the calculation of AlgorithmX solutions
import numpy as np
import pandas as pd
from AlgorithmX import *
from random import sample
from interruptingcow import timeout
import sys
import logging
TIMEOUT = 90
import random
random.seed(1000)

def const_mapper(df, log=None, log_df_name=None):
    """
    As the AlgorithmX code requires inputs starting from zero we shall take all values in the dataframes
    and map them to ints. This function will return the solver required.
    The df is always randomly resampled when we run this so that we get a different initial answer each time.
    """
    df = df.sample(len(df), random_state = int(random.random()*100000))
    name_cols = get_name_cols(df)
    const_list = np.unique(df[name_cols].stack())
    n = len(const_list)
    mapping = {}
    for i in range(n):
        mapping[const_list[i]] = i
    for col in name_cols:
        df = df.replace({col: mapping})
    file = log_df_name.replace("Logs/DataFrames", "Logs/check/").replace(".gz", "")
    df.to_csv(file, index=False)
    log.info("Written to csv")
    solver = AlgorithmX(n)
    log.info("Before for")
    k = 0
    for index, row in df.iterrows():
        k += 1
        try:
            with timeout(TIMEOUT, exception=RuntimeError): 
                if k % 100 == 0:
                    log.info(index)
                solver.appendRow([r for r in row[name_cols]], row['set_no'])
        except RuntimeError:
            log.info("Failed to create solver")
            solver = None
    log.info("Ended for loop")
    return solver

def return_solutions(df, max_soln = 1e7, resampled=False, log_df_name=None, log=None):
    """
    This function returns the solutions from the AlgorithmX code.
    prop - states what proportion of the solutions are returned (useful for when they get too big)
    max_soln - maximum number of solutions to derive
    resampled - is this solution being rerun
    """
    max_returned = 2.5e6
    
    df.to_csv(log_df_name, index=False)
    log.info("Start return_solutions")
    solver = const_mapper(df, log=log, log_df_name=log_df_name)
    log.info("After mapper")
    if solver is not None:
        solns = 0
        dict_solns = {}
        # save a copy of the dataframe used so that is can be investigated if there are issues
        try:
            with timeout(TIMEOUT, exception=RuntimeError): 
                # Stop calculations if taking too long, either there is no solution or having difficulty finding first one\
                log.info("Starting Algorithmx")
                for solution in solver.solve():
                    dict_solns[solns] = solution
                    if solution is None:
                        log.info("Exited with timeout")
                        solns = 0
                        break
                    else:
                        solns += 1
                        if solns == max_soln:
                            resampled = True # As we will be rerunning this with a 'resampled' data frame
                            break
                soln_returned = solns > 0
                log.info(f"Finished Algorithmx with soln_returned={soln_returned} and resampled={resampled}")

                # If the result is too big take a sample. If the solution is going to be resampled take a small proportion
                # otherwise take a larger one
                if soln_returned:
                    if not resampled and solns <= max_returned:
                        sampled_solns = pd.DataFrame({'soln': dict_solns}).reset_index(drop=True)
                    else:
                        if not resampled:
                            keys = sample(list(dict_solns.keys()), max_returned)
                        else:
                            keys = sample(list(dict_solns.keys()), int(max_soln*0.0025))
                        dict_solns2 = {}
                        for k in keys:
                            dict_solns2[k] = dict_solns[k]
                        sampled_solns = pd.DataFrame({'soln': dict_solns2}).reset_index(drop=True)
                    # Sort out the solutions at this point to save time later.
                    log.info("Sampled solutions obtained")
                    sampled_solns = sampled_solns.assign(soln = [list(np.sort(s)) for s in sampled_solns['soln']])
                    log.info("Sampled solutions sorted")
                    return soln_returned, sampled_solns, resampled
                else:
#                     soln_returned = False
                    return soln_returned, None, None
        except RuntimeError:
            log.info("Algorithm took too long")
            soln_returned = False
            return soln_returned, None, None
    else:
        log.info("Mapper took too long")
        soln_returned = False
        return soln_returned, None, None
        
    # Need to add in the following:
    # 1. Stop when solutions become too big, rerun with resampled df and take sample of that - DONE
    # 2. when we remove some other random constituencies how do we rerun it and run it multiple times
    #        - need a counter to ensure we get a solution too - DONE
    # 3. how do we cope with zero solutions, e.g. Yorkshire when we have triplets
    #        - Have added a check to ensure that number of remaining constituencies is equal to no of merged seats
    #          This won't solve the problem with the triplets and Yorkshire, but should ensure that when we
    #          have to remove multiple triplets that it should get a result.
        

def to_remove_names(df):
    """
    from the randomly selected 'set_no' put the names that will be removed into a list
    """
    return df.loc[:, df.columns.str.startswith('name')].values.tolist()[0]

def get_n(df, name_cols):
    """
    Find how many different constituencies there are in a data frame.
    """
    const_list = np.unique(df[name_cols].stack())
    return len(const_list)

def remove_consts(df, to_remove, name_cols):
    """
    Given a list of constituencies (to_remove) remove all rows from dataframe which contain them
    """
    for name in name_cols:
        df = df[~df[name].isin(to_remove)]
    return df

def get_name_cols(df):
    """
    Return all columns that start with the word 'name'
    """
    return df.columns[df.columns.str.startswith('name')]

def remove_random_const(const_pairs, const_tris, const_quads, seats, region, n):
    """
    This function removes randomly selected pairs / triplets / quadruplets to make sure
    that the number of constituencies left are divisble by the number of seats.
    """
    n2 = n # Check that the number of remaining constituencies are divisible by n
    if seats == 2:
        name_cols = get_name_cols(const_pairs)
    elif seats == 3:
        name_cols = get_name_cols(const_tris)
    elif seats == 4:
        name_cols = get_name_cols(const_quads)
    removed = {}
    if seats == 2:
        while n2 % seats != 0:
            df = const_pairs.copy()
            random_const = const_tris.sample(1, random_state=int(random.random()*1000000))
            removed['triplet'] = random_const['set_no'].iloc[0]
            to_remove = to_remove_names(random_const)
            df = remove_consts(df, to_remove, name_cols)
            n2 = get_n(df, name_cols)
    elif seats == 3:
        while n2 % seats != 0:
            df = const_tris.copy()
            if (seats == 3) & (n % seats == 1):
                random_const = const_quads.sample(1, random_state=int(random.random()*1000000))
                removed['quad'] = random_const['set_no'].iloc[0]
                to_remove = to_remove_names(random_const)
            elif (seats == 3) & (n % seats == 2):
                random_const = const_pairs.sample(1, random_state=int(random.random()*1000000))
                removed['pair'] = random_const['set_no'].iloc[0]
                to_remove = to_remove_names(random_const)
            df = remove_consts(df, to_remove, name_cols)
            n2 = get_n(df, name_cols)
    elif seats == 4:
        while n2 % seats != 0:
            df = const_quads.copy()
            # Need to ensure that when we remove multiple triplets that none of the elements are repeated
            if (n % seats == 2) or (n % seats == 1):
                df2 = const_tris.copy()
                name_cols2 = df2.columns[df2.columns.str.startswith('name')]
                if n % seats == 1:
                    # remove 3 triplets
                    trips = 3
                elif n % seats == 2:
                    # remove 2 triplets
                    trips = 2
                to_remove = []
                for i in range(trips):
                    random_const = df2.sample(1, random_state=int(random.random()*1000000))
                    if i == 0:
                        removed['triplet'] = [random_const['set_no'].iloc[0]]
                    else:
                        removed['triplet'] = [*removed['triplet'], random_const['set_no'].iloc[0]]
                    to_remove = to_remove + to_remove_names(random_const)
                removed['triplet'] = list(np.sort(removed['triplet']))
                for name in name_cols2:
                    df2 = df2[~df2[name].isin(to_remove)]
            elif n % seats == 3:
                random_const = const_tris.sample(1, random_state=int(random.random()*1000000))
                removed['triplet'] = random_const['set_no'].iloc[0]
                to_remove = to_remove_names(random_const)
            df = remove_consts(df, to_remove, name_cols)
            n2 = get_n(df, name_cols)

    return df, removed

def custom_logger(logger_name, level=logging.DEBUG):
    """
    Method to return a custom logger with the given name and level
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    format_string = ('%(levelname)s: %(asctime)s: %(message)s')
    log_format = logging.Formatter(format_string)
    # Creating and adding the console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    # Creating and adding the file handler
    file_handler = logging.FileHandler(logger_name, mode='a')
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    return logger

def get_solns(const_pairs, const_tris, const_quads, seats, region, max_solns=1e6):
    """
    Find the solutions, or a subset of them, and saves them into a csv file
    """
    const_pairs2 = const_pairs.query("region == @region")
    const_tris2 = const_tris.query("region == @region")
    const_quads2 = const_quads.query("region == @region")
    if seats == 2:
        df = const_pairs2
    elif seats == 3:
        df = const_tris2
    elif seats == 4:
        df = const_quads2
    name_cols = get_name_cols(df)
    # How many times should we rerun Algorithm X when we cannot return all solutions.
    RERUN_COUNTER = 5 #* (1 + (seats >= 4))
    # How many times should we rerun Algorithm X when we have to remove different sized sets.
    COUNTER = 5 #* (1 + (seats >= 4))
    LONG_TIMEOUT = 180
    
    n = get_n(df, name_cols)
    r = region.replace(" ", "_")
    file_name = f"Solutions/solns_{r}_{seats}.csv.gz"
    log_file_name = f"Logs/log_{r}_{seats}.log"
    log_df_name = f"Logs/DataFrames/df_{r}_{seats}.csv.gz"
    log = custom_logger(log_file_name)
    log.info(f'Starting code for region {region} with {seats} seats.')
    if n % seats == 0:
        try:
            with timeout(LONG_TIMEOUT, exception=RuntimeError): 
                soln_returned, solns, resampled = return_solutions(df, resampled=False, max_soln=max_solns, log_df_name=log_df_name, log=log)
                log.info(f"For n % seats == 0 we have soln_returned={soln_returned} and resampled={resampled}.")
        except RuntimeError:
                log.warning(f"For the {region} region, when we have {seats} seats there is a timeout.")
                soln_returned = False
        if soln_returned:
            if len(solns) <= 1 or solns is None:
                log.warning(f"For the {region} region, when we have {seats} seats there are no solutions.")
            else:
                # If we're unable to get all solutions rerun multiple times to get a further subset of them.
                if resampled:
                    d = {}
                    d[0] = solns.copy()
                    j = 0
                    while j < RERUN_COUNTER: # and soln_returned:
                        log.info(f"At j = {j}.") # with soln_returned = {soln_returned}.")
                        try:
                            with timeout(LONG_TIMEOUT, exception=RuntimeError): 
                                soln_returned, d[j], resampled = return_solutions(df, resampled=True, max_soln=max_solns, log_df_name=log_df_name, log=log)
                        except RuntimeError:
                                log.warning(f"For the {region} region, when we have {seats} seats there is a timeout.")
                                soln_returned = False
                        log.info(f"For j={j} we have soln_returned={soln_returned} and resampled={resampled}.")
                        j += 1
                    if soln_returned:
                        try:
                            solns = pd.concat(d, ignore_index=True)
                        except:
                            log.warning(f"For region {region} with seats = {seats} we cannot concatenate.")
                            for k in range(len(d)):
                                f = f"Logs/check/soln_{r}_{seats}_d_{i}_{k}.csv"
                                log.warning(f"{k}: {d[k].shape} saved to {f}")
                                d[k].to_csv(f, index=False)
        else:
            log.warning(f"Issue with the {region} region, when we have {seats} seats there are no solutions returned.")
    else:
        # Get the solutions multiple times with different random elements removed.
        soln_dict = {}
        i = 0
        while i <= COUNTER:
            df, removed = remove_random_const(const_pairs2, const_tris2, const_quads2, seats, region, n)
            try:
                with timeout(LONG_TIMEOUT, exception=RuntimeError): 
                    soln_returned, soln_dict[i], resampled = return_solutions(df, resampled=False, max_soln=max_solns, log_df_name=log_df_name, log=log)
                    log.info(f"For i={i} we have soln_returned={soln_returned} and resampled={resampled}.")
            except RuntimeError:
                log.warning(f"For the {region} region, when we have {seats} seats there is a timeout.")
                soln_returned = False
            if soln_returned:
                if resampled:
                    d = {}
                    d[0] = soln_dict[i].copy()
                    try:
                        d[0].to_csv(f"Logs/solns/soln_{r}_{seats}_d_0.csv", index=False)
                    except:
                        log.warning(f"For region {region} with seats = {seats} we cannot get a solution for d[0]")
                    j = 0
                    while j < RERUN_COUNTER: # and soln_returned:
                        log.info(f"At j = {j}.") # with soln_returned = {soln_returned}.")
                        try:
                            with timeout(LONG_TIMEOUT, exception=RuntimeError): 
                                log.info("Before getting solutions.")
                                soln_returned, d[j], resampled = return_solutions(df, resampled=True, max_soln=max_solns, log_df_name=log_df_name, log=log)
                                log.info(f"For j={j} we have soln_returned={soln_returned} and resampled={resampled}.")
                        except RuntimeError:
                                log.warning(f"For the {region} region, when we have {seats} seats there is a timeout.")
                                soln_returned = False
                        if soln_returned:
                            log.info(f"Need to write file to Logs/solns/soln_{r}_{seats}_d_{i}_{j}.csv")
                            log.info(f"Solution is of size {d[j].shape}")
                            try:
                                d[j].to_csv(f"Logs/solns/soln_{r}_{seats}_d_{i}_{j}.csv", index=False)
                            except:
                                log.warning(f"For region {region} with seats = {seats} we cannot get a solution for d[{j}]")
                            log.info(f"Finished writing file to Logs/solns/soln_{r}_{seats}_d_{i}_{j}.csv")
                            j += 1
                    log.info(f"Finished finding solutions for region {region} with {seats} seats having soln_returned = {soln_returned}.")
                    if soln_returned:
                        log.info(f"Before concatenation.")
                        try:
                            soln_dict[i] = pd.concat(d, ignore_index=True)
                        except:
                            log.warning(f"For region {region} with seats = {seats} we cannot concatenate.")
                            for k in range(len(d)):
                                f = f"Logs/check/soln_{r}_{seats}_d_{i}_{k}.csv"
                                log.warning(f"{k}: {d[k].shape} saved to {f}")
                                d[k].to_csv(f, index=False)
                else:
                    soln_dict[i].to_csv(f"Logs/solns/soln_{r}_{seats}_d_{i}.csv", index=False)
            if soln_returned:
                try:
                    # Add in the set_no's that were removed from the solutions
                    soln_dict[i][list(removed.keys())[0]] = str(list(removed.values())[0])
                    i += 1
                except:
                    for k in range(len(soln_dict)):
                        log.warning(f"{k}: {soln_dict[k].shape}")
                    log.warning(f"For region {region} with seats = {seats} we cannot add in the removed solutions.")
        try:
            solns = pd.concat(soln_dict, ignore_index=True)
        except:
            for k in range(len(soln_dict)):
                log.warning(f"{k}: {soln_dict[k].shape}")
            log.warning(f"For region {region} with seats = {seats} we cannot concatenate solutions.")
    try:
        if len(solns) > 0:
            solns = solns.assign(region = region)
    #         # Sort the solutions (to save us having to do it later)
    #         solns = solns.assign(sorted_soln = [list(np.sort(t)) for t in solns['soln']])
            solns.to_csv(file_name, index=False, compression='gzip')
            log.info(f"Finished getting solutions for region {region} with {seats} seats")
    except:
        log.warning(f"Cannot get solutions for region {region} with {seats} seats")
