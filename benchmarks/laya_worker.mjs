// Keep the installed CPU model warm for a fair local inference timing comparison.
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {dirname,join} from 'node:path';
import readline from 'node:readline';
const require=createRequire(join(dirname(process.argv[2]),'package.json'));
const {Laya}=await import(pathToFileURL(require.resolve('@receptron/laya')).href);
const started=performance.now();
const model=await Laya.load({executionProviders:['cpu'],sessionOptions:{intraOpNumThreads:4}});
console.log(JSON.stringify({ready:true,startup_ms:performance.now()-started}));
const input=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
try {
  for await(const line of input) {
    let request;
    try {
      request=JSON.parse(line);
      const start=performance.now();
      const result=await model.systemOne(request.state,request.questions);
      console.log(JSON.stringify({id:request.id,result,elapsed_ms:performance.now()-start}));
    } catch(error) {
      console.log(JSON.stringify({id:request?.id,error:error.message}));
    }
  }
} finally {await model.close();}
