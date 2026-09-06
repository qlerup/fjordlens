"""Calendar hints for Danish celebrations, based on capture dates, not image claims."""
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache


def easter_sunday(year):
    # Gregorian computus.
    a=year%19; b=year//100; c=year%100; d=b//4; e=b%4
    f=(b+8)//25; g=(b-f+1)//3; h=(19*a+b-d-g+15)%30
    i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    n=h+l-7*m+114
    return date(year,n//31,n%31+1)


@lru_cache(maxsize=128)
def danish_days(year):
    days = {}
    for month, day, name, group in [(1,1,'Nytårsdag','Nytår'), (12,31,'Nytårsaften','Nytår'),
            (12,24,'Juleaften','Jul'), (12,25,'Juledag','Jul'), (12,26,'Anden juledag','Jul'),
            (6,5,'Grundlovsdag','Grundlovsdag'), (6,23,'Sankthansaften','Sankt Hans')]:
        days[date(year,month,day)] = (name,group)
    easter = easter_sunday(year)
    for offset,name,group in [(-3,'Skærtorsdag','Påske'),(-2,'Langfredag','Påske'),
            (0,'Påskedag','Påske'),(1,'Anden påskedag','Påske'),(39,'Kristi himmelfartsdag','Kristi himmelfart'),
            (49,'Pinsedag','Pinse'),(50,'Anden pinsedag','Pinse')]:
        days[easter+timedelta(days=offset)] = (name,group)
    return days


def occasion_for_dates(dates, countries=()):
    if not dates:
        return None
    # Danish local dates are used at home or when the location is unknown.
    # Abroad, only the common Christmas/New Year hints are applied.
    local = not countries or set(countries) == {'DK'}
    hits = [(day,danish_days(day.year).get(day)) for day in dates]
    hits = [(day,info) for day,info in hits if info and (local or info[1] in ('Jul','Nytår'))]
    if not hits:
        return None
    group,count = Counter(info[1] for _,info in hits).most_common(1)[0]
    if count < len(dates)*.6:
        return None
    matching = [(day,info) for day,info in hits if info[1] == group]
    unique_days = {day for day,_ in matching}
    if (max(unique_days)-min(unique_days)).days > 7:
        return None
    name = matching[0][1][0] if len(unique_days) == 1 else group
    return dict(name=name,group=group,calendar='DK' if local else 'Christmas/New Year',
                basis='capture_date',photo_matches=count,year=min(unique_days).year)


def title_for(occasion, place=None):
    return f"{occasion['name']} i {place}" if place else f"{occasion['name']} {occasion['year']}"
