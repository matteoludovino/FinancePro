package br.com.finance.FinancePro.financias.Valor.Controller;

import br.com.finance.FinancePro.financias.Valor.Model.ValoresModel;
import br.com.finance.FinancePro.financias.Valor.Service.ValoresService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/valores")
public class ValoresController {

    private final ValoresService valoresService;

    public ValoresController(ValoresService valoresService) {this.valoresService = valoresService;}

    @GetMapping
    public List<ValoresModel> getAll() {return valoresService.getAll();}

    @PostMapping
    public ValoresModel create(@RequestBody ValoresModel valoresModel) {return valoresService.save(valoresModel);}

    @DeleteMapping("/{id}")
    public void delete(@PathVariable long id) {valoresService.delete(id);}
}
