from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float
from sqlalchemy.sql import func
from smos.core.database import Base

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String, nullable=True)
    author_id = Column(Integer, ForeignKey("cosmonauts.id"))
    contributors = Column(JSON, default=[])
    problem_type = Column(String)
    steps = Column(JSON, default=[])
    required_agents = Column(JSON, default=[])
    required_skills = Column(JSON, default=[])
    required_tools = Column(JSON, default=[])
    success_conditions = Column(JSON, default=[])
    prerequisites = Column(JSON, default=[])
    resources = Column(JSON, default=[])
    outcome = Column(String, nullable=True)
    confidence = Column(Float, default=1.0)
    success_rate = Column(Float, default=0.0)

    # Evolution
    parent_recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True)
    mutations = Column(JSON, default=[])

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RecipeExecution(Base):
    __tablename__ = "recipe_executions"
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    participants = Column(JSON, default=[]) # List of cosmonaut IDs
    result = Column(String) # SUCCESS, FAILURE
    duration = Column(Float, nullable=True)
    cost = Column(Float, default=0.0)
    satisfaction = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Wisdom(Base):
    __tablename__ = "wisdom"
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    evidence = Column(JSON, default=[])
    confidence = Column(Float, default=1.0)
    domains = Column(JSON, default=[])
    generations = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AntiRecipe(Base):
    __tablename__ = "anti_recipes"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    triggers = Column(JSON, default=[])
    failure_pattern = Column(String)
    warning_signs = Column(JSON, default=[])
    reconstruction_id = Column(Integer, ForeignKey("reconstructions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Reconstruction(Base):
    __tablename__ = "reconstructions"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    observations = Column(JSON, default=[])
    artifacts = Column(JSON, default=[])
    witnesses = Column(JSON, default=[])
    evidence_level = Column(String, default="DIRECT") # DIRECT, INDIRECT, RECONSTRUCTED, DEDUCED, SIMULATED
    hypotheses = Column(JSON, default=[])
    inferred_facts = Column(JSON, default=[])
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CausalRelation(Base):
    __tablename__ = "causal_relations"
    id = Column(Integer, primary_key=True, index=True)
    cause_node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    effect_node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    confidence = Column(Float, default=1.0)
    evidence = Column(JSON, default=[])
