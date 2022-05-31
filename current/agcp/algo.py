from .model import *


def policy_shadow(policies: List[Policy], containers: List[Container]) -> List[Tuple[int, int]]:

    for i, container in enumerate(containers):
        shad_pols=[]
        cont_sel_pols = []
        polsEg =  container.select_policies
        polsIng =  container.allow_policies
        for m, poEg in enumerate(policies):
            if m in polsEg:
                cont_sel_pols.append(poEg)

        for m, poIng in enumerate(policies):
            if m in polsIng:
                cont_sel_pols.append(poIng)

        for j, pj in enumerate(cont_sel_pols):
            for k, pk in enumerate(cont_sel_pols):

                if j == k:
                    continue

                if pj.direction == pk.direction== PolicyEgress:
                    if pj.working_select_set == pk.working_select_set: ## need to include subset to equality
                        j_allow = pj.working_allow_set
                        k_allow = pk.working_allow_set
                        if ((j_allow  & k_allow) ^ k_allow).count() == 0:
                            shad_pols.append((pj.name, pk.name)) ## need to add indices instead of names


                        '''pj.working_select_set >= pk.working_select_set or \
                        pj.working_select_set <= pk.working_select_set:
                        j_allow = pj.working_allow_set
                        k_allow = pk.working_allow_set
                        if ((j_allow  & k_allow) ^ k_allow).count() == 0:
                            shad_pols.append((pj.name, pk.name))'''

                        '''    for a, b in enumerate(policies):
                                for c, d in enumerate(policies):
                                    if b == pj and d == pk:
                                        shad_pols.append((a, c))'''

                if pj.direction == pk.direction== PolicyIngress:
                    if pj.working_allow_set == pk.working_allow_set:
                        j_allow = pj.working_select_set
                        k_allow = pk.working_select_set
                        if ((j_allow  & k_allow) ^ k_allow).count() == 0:
                            shad_pols.append((pj.name, pk.name))

    return shad_pols  ##sometimes returns two same policies



def policy_conflict( policies: List[Policy], containers: List[Container]) -> List[Tuple[int, int]]: 
    """
    Policy conflict.
    The connections built by a policy are totally contradict the connections built by another
    """

    for i, container in enumerate(containers):
        conf_pols=[]
        cont_sel_pols = []
        polsEg =  container.select_policies
        polsIng =  container.allow_policies
        for m, poEg in enumerate(policies):
            if m in polsEg:
                cont_sel_pols.append(poEg)

        for m, poIng in enumerate(policies):
            if m in polsIng:
                cont_sel_pols.append(poIng)

        for j, pj in enumerate(cont_sel_pols):
            for k, pk in enumerate(cont_sel_pols):
                if j == k:
                    continue

                if pj.direction == pk.direction== PolicyEgress:
                    if pj.working_select_set == pk.working_select_set:
                        j_disallow = ~ pj.working_allow_set
                        k_allow = pk.working_allow_set
                        if ((j_disallow  & k_allow) ^ k_allow).count() == 0:
                            conf_pols.append((pj.name, pk.name))

                if pj.direction == pk.direction== PolicyIngress:
                    if pj.working_allow_set == pk.working_allow_set:
                        j_disallow = ~ pj.working_select_set
                        k_allow = pk.working_select_set
                        if ((j_disallow  & k_allow) ^ k_allow).count() == 0:
                            conf_pols.append((pj.name, pk.name))

    return conf_pols


def over_permissive(containers: List[Container], policies: List[Policy]) -> List[int]: # To be updated
    n_container = len(containers)
    labelMap: Dict[str, bitarray] = DefaultDict(lambda: bitarray('0' * n_container))
    perm_pols = []

    for i, container in enumerate(containers):
        for key, value in container.labels.items():
            labelMap[key][i] = True

    for i, policy in enumerate(policies):
        select_set = bitarray(n_container)
        select_set.setall(True)
        allow_set = bitarray(n_container)
        allow_set.setall(True)

        for k, v in policy.working_selector.labels.items():
            if k in labelMap.keys(): #all keys in containers
                select_set &= labelMap[k]

            else:
                if not policy.working_selector.labels:
                    continue
                select_set.setall(False)


        for items in  policy.working_allow:
            for k, v in items.labels.items():
                if k in labelMap.keys():
                    allow_set &= labelMap[k]

        for idx, cont_info in enumerate (containers):#in range(n_container):
            if select_set[idx] and not policy.select_policy(containers[idx]):
                select_set[idx] = False

            if allow_set[idx] and not policy.allow_policy(containers[idx]):
                allow_set[idx] = False
        if any(select_set) or any(allow_set): #If select set or allow set is all True
            perm_pols.append(i)

    return perm_pols

