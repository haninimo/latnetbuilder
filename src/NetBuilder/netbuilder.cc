// This file is part of LatNet Builder.
//
// Copyright (C) 2012-2018  Pierre L'Ecuyer and Universite de Montreal
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


#include <fstream>
#include <chrono>
#include <boost/program_options.hpp>
#include <boost/lexical_cast.hpp>
#include <iostream>

#include "netbuilder/Types.h"
#include "netbuilder/Parser/CommandLine.h"
#include "netbuilder/Parser/EmbeddingTypeParser.h"
#include "netbuilder/Parser/NetConstructionParser.h"
#include "netbuilder/Parser/OutputFormat.h"
#include "netbuilder/Task/Task.h"

#include "latbuilder/Parser/Common.h"
#include "latbuilder/SizeParam.h"

// using namespace LatBuilder;
// using TextStream::operator<<;

namespace NetBuilder{
static unsigned int merit_digits_displayed = 0;

void TaskOutput(const Task::Task &task, std::vector<Parser::OutputFormatParameters>& vecOutputFormatParameters)
{
  unsigned int old_precision = (unsigned int)std::cout.precision();
  if (merit_digits_displayed){
    std::cout.precision(merit_digits_displayed);
  }
  std::cout << task.outputNet(OutputFormat::CLI) << "merit: " << task.outputMeritValue() << std::endl;

  for (Parser::OutputFormatParameters outputFormatParameters : vecOutputFormatParameters){
    ofstream outFile;
    std::string fileName = outputFormatParameters.file();
    outFile.open(fileName);
    outFile << task.outputNet(outputFormatParameters.outputFormat());
    outFile.close();
  }
  
  if (merit_digits_displayed){
    std::cout.precision(old_precision);
  }
}

boost::program_options::options_description
makeOptionsDescription()
{
   namespace po = boost::program_options;
   po::options_description desc("allowed options");

   desc.add_options ()
    ("set-type,T", po::value<std::string>(),
    "(required) point set type; possible values:\n"
    "  lattice\n"
    "  net\n")
   ("help,h", "produce help message")
   ("version,V", "show version")
   ("verbose,v", po::value<std::string>()->default_value("0"),
   "specify the verbosity of the program\n")
   ("construction,c", po::value<std::string>()->default_value("sobol"),
   "digital net; possible constructions:\n"
   "  sobol (default)\n"
   "  polynomial:<modulus>\n"
   "  explicit:<matrix-size>\n")
   ("multilevel,m", po::value<std::string>()->default_value("false"),
    "multilevel point set; possible values:\n"
   "  false (default)\n"
   "  true\n")
   ("size,s", po::value<std::string>(),
    "(required) size of the net; possible values:\n"
   "  <size>\n"
   "  2^<max-power>\n")
   ("exploration-method,E", po::value<std::string>(),
    "(required) exploration method; possible values:\n"
    "  evaluation:<net_description>\n" 
    "  exhaustive\n"
    "  random:<r>\n"
    "  full-CBC\n"
    "  random-CBC:<r>\n"
    "  mixed-CBC:<r>:<nb_full>\n"
    "where <r> is the number of randomizations, and <nb_full> the number of coordinates for which full CBC exploration is used.")
    ("dimension,d", po::value<std::string>(),
    "(required) net dimension\n")
    ("merit-digits-displayed", po::value<unsigned int>()->default_value(0),
    "(optional) number of significant figures to use when displaying merit values\n")
   ("weights-power,o", po::value<Real>(),
    "(default: same value as for the --norm-type argument) real number specifying that the weights passed as input will be assumed to be already elevated at that power (a value of `inf' is mapped to 1)\n")
    ("combiner,b", po::value<std::string>(),
    "combiner for (filtered) multilevel merit values; possible values:\n"
    "  sum\n"
    "  max\n"
    "  level:{<level>|max}\n")
    ("figure-combiner,B", po::value<std::string>()->default_value("max"),
    "combiner for combined figure of merit; possible values: \n"
    "  sum\n"
    "  max (default)\n")
    ("add-figure,a", po::value< std::vector<std::string> >()->composing(),
    "(at least one required) add one type of figure of merits. If several, specify a figure combiner.\n"
    "Syntax pattern:\n"
    " \n" // TODO
    "where name can take the following values:\n"
    "resolution-gap, t-value,  and CU:P2\n")
  //  ("filters,f", po::value<std::vector<std::string>>()->multitoken(),
  //   "whitespace-separated list of filters for merit values; possible values:\n"
  //   "  norm:P<alpha>-{SL10|DPW08}\n"
  //   "  low-pass:<threshold>\n")
  //  ("multilevel-filters,F", po::value<std::vector<std::string>>()->multitoken(),
  //   "whitespace-separated list of filters for multilevel merit values; possible values:\n"
  //   "  norm:P<alpha>-{SL10|DPW08}[:<multilevel-weights>]\n"
  //   "  low-pass:<threshold>\n"
  //   "where <multilevel-weights> specifies the per-level weights; possible values:\n"
  //   "  even[:<min-level>[:<max-level>]] (default)\n")
   ("no-early-abort,e", "(optional) disable early abortion in computations.")
    ("output-format,g", po::value< std::vector<std::string> >()->composing(),
    "(optional) output generator matrices of the resulting polynomial lattice as a digital net, in the indicated format; possible values:\n"
   "  file:\"<file>\":format\n"
   "  available output formats\n"
   "  - ssj \n"
   "  - cli \n"
   "  - gui \n")
   ("repeat,r", po::value<unsigned int>()->default_value(1),
    "(optional) number of times the construction must be executed\n"
   "(can be useful to obtain different results from random constructions)\n");

   return desc;
}


boost::program_options::variables_map
parse(int argc, const char* argv[])
{
   namespace po = boost::program_options;

   auto desc = makeOptionsDescription();

   po::variables_map opt;
   po::store(po::parse_command_line(argc, argv, desc), opt);
   po::notify(opt);

   if (opt.count("help")) {
      std::cout << desc << std::endl;
      std::exit (0);
   }

   if (opt.count("add-figure") < 1)
      throw std::runtime_error("--add-figure must be specified (try --help)");
   for (const auto x : {"size", "exploration-method", "dimension"}) {
      if (opt.count(x) != 1)
         throw std::runtime_error("--" + std::string(x) + " must be specified exactly once (try --help)");
   }
   if (opt.count("add-figure") >= 2 && opt.count("figure-combiner") != 1)
      throw std::runtime_error("--figure-combiner must be specified (try --help)");

    if (opt["set-type"].as<std::string>() == "sequence" && ! opt.count("combiner")){
      throw std::runtime_error("--combiner must be specified for sequence set type (try --help)");
    }
   return opt;
}


#define BUILD_TASK(net_construction, point_set_type)\
NetBuilder::Parser::CommandLine<NetBuilder::NetConstruction::net_construction, NetBuilder::EmbeddingType::point_set_type> cmd;\
\
cmd.s_designParameter = designParameterString;\
cmd.s_verbose = opt["verbose"].as<std::string>();\
cmd.s_explorationMethod = opt["exploration-method"].as<std::string>();\
cmd.s_size = opt["size"].as<std::string>();\
cmd.s_dimension = opt["dimension"].as<std::string>();\
cmd.s_figures = opt["add-figure"].as<std::vector<std::string>>();\
if (opt.count("figure-combiner") < 1){\
  cmd.s_figureCombiner = "";\
}\
else{\
  cmd.s_figureCombiner = opt["figure-combiner"].as<std::string>();\
}\
if (opt.count("combiner") < 1){\
  cmd.s_combiner = "";\
}\
else{\
  cmd.s_combiner = opt["combiner"].as<std::string>();\
}\
if (opt.count("no-early-abort") >= 1){\
  cmd.m_earlyAbort = false;\
}\
else{\
  cmd.m_earlyAbort = true;\
}\
if (opt.count("weight-power") == 1 ){\
  cmd.m_hasWeightPower = true; \
  cmd.m_weightPower = boost::lexical_cast<Real>(opt["weight-power"].as<std::string>());\
}\
else{\
  cmd.m_hasWeightPower = false;\
}\
task = cmd.parse();




int main(int argc, const char *argv[])
{

   try {
     using namespace std::chrono;
     const std::string separator = "\n--------------------------------------------------------------------------------\n";


        auto opt = parse(argc, argv);

        auto repeat = opt["repeat"].as<unsigned int>();

        // NetBuilder::OutputFormat outputFormat;
        std::vector<NetBuilder::Parser::OutputFormatParameters> outputFormatParameters;
        if (opt.count("output-format") >= 1){
          outputFormatParameters = Parser::OutputFormatParser::parse(opt["output-format"].as<std::vector<std::string>>());
        }
        else{
          outputFormatParameters = {};
        }
        
        // global variable
        merit_digits_displayed = opt["merit-digits-displayed"].as<unsigned int>();

        std::string s_multilevel = opt["multilevel"].as<std::string>();
        std::string s_construction = opt["construction"].as<std::string>();
        NetBuilder::EmbeddingType embeddingType = NetBuilder::Parser::EmbeddingTypeParser::parse(s_multilevel);

        std::pair<NetBuilder::NetConstruction,std::string> netConstructionPair;

        if (embeddingType==NetBuilder::EmbeddingType::UNILEVEL)
        {
          netConstructionPair =  NetBuilder::Parser::NetConstructionParser<NetBuilder::EmbeddingType::UNILEVEL>::parse(s_construction);
        }
        else
        {
          netConstructionPair =  NetBuilder::Parser::NetConstructionParser<NetBuilder::EmbeddingType::MULTILEVEL>::parse(s_construction);
        }

        NetBuilder::NetConstruction netConstruction = netConstructionPair.first;

        std::string designParameterString = netConstructionPair.second;

        std::chrono::time_point<std::chrono::high_resolution_clock> t0, t1;
      
        std::unique_ptr<NetBuilder::Task::Task> task;

        if(netConstruction == NetBuilder::NetConstruction::SOBOL && embeddingType == NetBuilder::EmbeddingType::UNILEVEL){
          BUILD_TASK(SOBOL, UNILEVEL)
       }
       if(netConstruction == NetBuilder::NetConstruction::SOBOL && embeddingType == NetBuilder::EmbeddingType::MULTILEVEL){
          BUILD_TASK(SOBOL, MULTILEVEL)
       }
       if(netConstruction == NetBuilder::NetConstruction::POLYNOMIAL && embeddingType == NetBuilder::EmbeddingType::UNILEVEL){
          BUILD_TASK(POLYNOMIAL, UNILEVEL)
       }
      //  if(netConstruction == NetBuilder::NetConstruction::POLYNOMIAL && embeddingType == NetBuilder::EmbeddingType::MULTILEVEL){
      //     BUILD_TASK(POLYNOMIAL, MULTILEVEL)
      //  }
        if(netConstruction == NetBuilder::NetConstruction::EXPLICIT && embeddingType == NetBuilder::EmbeddingType::UNILEVEL){
          BUILD_TASK(EXPLICIT, UNILEVEL)
       }
      //  if(netConstruction == NetBuilder::NetConstruction::EXPLICIT && embeddingType == NetBuilder::EmbeddingType::MULTILEVEL){
      //     BUILD_TASK(EXPLICIT, MULTILEVEL)
      //  }
      for (unsigned i=0; i<repeat; i++){
      t0 = high_resolution_clock::now();\
      task->execute();\
      t1 = high_resolution_clock::now();\
      TaskOutput(*task, outputFormatParameters);
      auto dt = duration_cast<duration<double>>(t1 - t0);
      std::cout << std::endl;
      std::cout << "ELAPSED CPU TIME: " << dt.count() << " seconds" << std::endl;
      task.reset();
      }
   }
   catch (LatBuilder::Parser::ParserError& e) {
      std::cerr << "COMMAND LINE ERROR: " << e.what() << std::endl;
      std::exit(1);
   }
   catch (std::exception& e) {
      std::cerr << "ERROR: " << e.what() << std::endl;
      std::exit(1);
   }

   return 0;
}

#undef BUILD_TASK
}