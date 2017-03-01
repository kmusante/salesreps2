import os
import sys 
from sqlalchemy import Column, ForeignKey, Integer, String #helper for mapper code
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship #for foreign key relationship
from sqlalchemy import create_engine #for configuration code

Base = declarative_base()  #lets sqlalchemy know something about this

# this is my User class so users may only modify things they have added
class User(Base):
    __tablename__='user'

    id=Column(Integer, primary_key=True)
    name=Column(String(250), nullable=False)
    email=Column(String(250), nullable=False)
    picture=Column(String(250))

   
class SalesReps(Base):
    __tablename__ = 'sales_reps' #identifies variable we will use when referring to database
   
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False) #false means this column must have a value
    user_id=Column(Integer, ForeignKey('user.id'))
    user=relationship(User)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'name': self.name,
            'user_id': self.user_id,
            'user': self.user
        } 
        
class RepDetails(Base):
    __tablename__ = 'rep_details'

    name =Column(String(80), nullable = False)
    payout=Column(Integer, nullable=False)
    sub_reps=Column(String(3), nullable=False)
    contractor=Column(String(3), nullable=False)
    id = Column(Integer, primary_key = True)
    salesrep_id = Column(Integer, ForeignKey('sales_reps.id')) 
    #look inside sales_reps table and retrieve id number
    salesrep= relationship(SalesReps)
    user_id=Column(Integer, ForeignKey('user.id'))
    user=relationship(User)

    @property
    def serialize(self):
        #Returns object data in easily serializeable format
        return {
        'name': self.name, 
        'payout': self.payout,
        'sub_reps': self.sub_reps,
        'contractor': self.contractor,
        'id': self.id,
        'user_id': self.user_id
        }

 


engine = create_engine(
	'sqlite:///salesreptwo.db') #points to database we will use

Base.metadata.create_all(engine)
